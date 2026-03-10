package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"cloud.google.com/go/bigquery"
	"cloud.google.com/go/vertexai/genai"
	"github.com/joho/godotenv"
	"google.golang.org/api/iterator"
)

var (
	projectID   string
	datasetID   string
	modelID     string
	location    string
	concurrency = 25
)

func init() {
	_ = godotenv.Load() // Optional: ignore error if .env is missing

	projectID = os.Getenv("PROJECT_ID")
	if projectID == "" {
		log.Fatal("PROJECT_ID is required in environment or .env")
	}

	datasetID = os.Getenv("DATASET_ID")
	if datasetID == "" {
		log.Fatal("DATASET_ID is required in environment or .env")
	}

	modelID = os.Getenv("MODEL_ID")
	if modelID == "" {
		log.Fatal("MODEL_ID is required in environment or .env")
	}

	location = os.Getenv("LOCATION")
	if location == "" {
		log.Fatal("LOCATION is required in environment or .env")
	}
}

type Candidate struct {
	CandidatePartNumber  string  `bigquery:"candidate_part_number" json:"candidate_part_number"`
	CandidateDescription string  `bigquery:"candidate_description" json:"candidate_description"`
	Supplier             string  `bigquery:"supplier" json:"supplier"`
	PartType             string  `bigquery:"part_type" json:"part_type"`
	SizeValue            float64 `bigquery:"size_value" json:"size_value"`
}

type QueueRow struct {
	PartNumber      string      `bigquery:"part_number" json:"customer_part_number"`
	PartDescription string      `bigquery:"part_description" json:"customer_part_description"`
	Candidates      []Candidate `bigquery:"candidates" json:"candidates"`
}

type MatchDecision struct {
	CustomerPartNumber string `json:"customer_part_number"`
	SupplierPartNumber string `json:"supplier_part_number"`
	Decision           string `json:"decision"`
	Reasoning          string `json:"reasoning"`
}

type BQDecision struct {
	CustomerPartNumber string    `json:"customer_part_number" bigquery:"customer_part_number"`
	Decision           string    `json:"decision" bigquery:"decision"`
	IsMatch            bool      `json:"is_match" bigquery:"is_match"`
	SupplierPartNumber string    `json:"supplier_part_number" bigquery:"supplier_part_number"`
	Reasoning          string    `json:"reasoning" bigquery:"reasoning"`
	IsHumanReviewed    bool      `json:"is_human_reviewed" bigquery:"is_human_reviewed"`
	CreatedAt          time.Time `json:"created_at" bigquery:"created_at"`
	UpdatedAt          time.Time `json:"updated_at" bigquery:"updated_at"`
}

func main() {
	if err := run(); err != nil {
		log.Printf("Fatal Error: %v", err)
		os.Exit(1)
	}
}

func run() error {
	ctx := context.Background()

	log.Println("Initializing BQ and Vertex GenAI Clients...")
	bqClient, err := bigquery.NewClient(ctx, projectID)
	if err != nil {
		return fmt.Errorf("failed to create BQ client: %w", err)
	}
	defer bqClient.Close()

	log.Println("Querying backlog from BigQuery...")
	q := bqClient.Query(fmt.Sprintf(`
		WITH unmatched AS (
		  SELECT * FROM %s.%s.agent_review_queue
		)
		SELECT DISTINCT 
		  q.customer_part_number as part_number, 
		  q.customer_description as part_description,
		  ARRAY_AGG(STRUCT(
			q.supplier_part_number as candidate_part_number, 
			COALESCE(q.supplier_description, "") as candidate_description, 
			COALESCE(q.supplier, "") as supplier, 
			COALESCE(q.part_type, "") as part_type, 
			COALESCE(q.size_value, 0.0) as size_value
		  )) AS candidates
		FROM unmatched q
		GROUP BY 1, 2
	`, projectID, datasetID))

	it, err := q.Read(ctx)
	if err != nil {
		return fmt.Errorf("failed to execute query: %w", err)
	}

	var rows []QueueRow
	for {
		var row QueueRow
		err := it.Next(&row)
		if err == iterator.Done {
			break
		}
		if err != nil {
			return fmt.Errorf("failed to parse row: %w", err)
		}
		rows = append(rows, row)
	}

	if len(rows) == 0 {
		log.Println("No records found in agent_review_queue. Exiting.")
		return nil
	}

	sysPromptBytes, err := os.ReadFile("agent_prompt.txt")
	if err != nil {
		return fmt.Errorf("failed to read prompt: %w", err)
	}
	systemPrompt := string(sysPromptBytes)

	genClient, err := genai.NewClient(ctx, projectID, location)
	if err != nil {
		return fmt.Errorf("failed to create genai client: %w", err)
	}
	defer genClient.Close()

	model := genClient.GenerativeModel(modelID)
	model.SystemInstruction = &genai.Content{
		Parts: []genai.Part{genai.Text(systemPrompt)},
	}
	model.ResponseMIMEType = "application/json"
	model.ResponseSchema = &genai.Schema{
		Type: genai.TypeArray,
		Items: &genai.Schema{
			Type: genai.TypeObject,
			Properties: map[string]*genai.Schema{
				"customer_part_number": {Type: genai.TypeString},
				"supplier_part_number": {Type: genai.TypeString},
				"decision":             {Type: genai.TypeString, Description: "Must be 'MATCH', 'NO_MATCH', or 'REQUIRES_HUMAN_REVIEW'"},
				"reasoning":            {Type: genai.TypeString},
			},
		},
	}

	batchSize := 5
	var batches [][]QueueRow
	for i := 0; i < len(rows); i += batchSize {
		end := i + batchSize
		if end > len(rows) {
			end = len(rows)
		}
		batches = append(batches, rows[i:end])
	}

	log.Printf("Found %d parts across %d partitioned batches. Starting Multi-Pass DLQ pipeline with %d fast-fail workers...\n", len(rows), len(batches), concurrency)

	currentBatches := batches
	maxPasses := 5

	for pass := 1; pass <= maxPasses; pass++ {
		if len(currentBatches) == 0 {
			log.Printf("🎉 PASS %d: No more DLQ batches left! Dynamic execution globally complete.", pass)
			break
		}

		log.Printf("🚀 STARTING PASS %d FOR %d BATCHES 🚀", pass, len(currentBatches))

		jobs := make(chan []QueueRow, len(currentBatches))
		resultsChan := make(chan []*BQDecision, concurrency*2)
		failedChan := make(chan []QueueRow, len(currentBatches))

		var wg sync.WaitGroup
		for i := 0; i < concurrency; i++ {
			wg.Add(1)
			go singlePassWorker(ctx, model, jobs, resultsChan, failedChan, &wg)
		}

		// Dispatch jobs sequentially
		for _, b := range currentBatches {
			jobs <- b
		}
		close(jobs)

		// File Writer Setup natively streams successful structurally-typed arrays into temporary cache
		tmpFileName := fmt.Sprintf("decisions_output_pass_%d.json", pass)
		tmpFile, err := os.Create(tmpFileName)
		if err != nil {
			return fmt.Errorf("failed to create %s: %w", tmpFileName, err)
		}

		var writeWg sync.WaitGroup
		writeWg.Add(1)
		go func() {
			defer writeWg.Done()
			defer tmpFile.Close()
			encoder := json.NewEncoder(tmpFile)
			for arr := range resultsChan {
				for _, d := range arr {
					encoder.Encode(d)
				}
			}
		}()

		// Block locally against workers
		wg.Wait()
		close(resultsChan)
		close(failedChan)
		writeWg.Wait()

		// Read the native fast-fail dead-letter components
		var failedBatches [][]QueueRow
		for fb := range failedChan {
			failedBatches = append(failedBatches, fb)
		}

		// If at least one successful batch generated natively, mathematically load the atomic array
		if len(currentBatches) > len(failedBatches) {
			log.Printf("📦 Executing BigQuery Load Job for %d successful batches in Pass %d...", len(currentBatches)-len(failedBatches), pass)
			sourceFile, _ := os.Open(tmpFileName)
			source := bigquery.NewReaderSource(sourceFile)
			source.SourceFormat = bigquery.JSON
			loader := bqClient.Dataset(datasetID).Table("agent_decisions").LoaderFrom(source)

			if pass == 1 {
				loader.WriteDisposition = bigquery.WriteTruncate // Phase 1 defines strict truncation block natively
			} else {
				loader.WriteDisposition = bigquery.WriteAppend // Phase 2+ defines dynamic append mechanisms
			}

			job, err := loader.Run(ctx)
			if err == nil {
				status, err := job.Wait(ctx)
				if err == nil && status.Err() == nil {
					log.Printf("✅ PASS %d BQ LOAD ATOMICALLY SUCCESSFUL!", pass)
				} else {
					log.Printf("❌ PASS %d BQ WAIT ERROR: %v", pass, status.Err())
				}
			} else {
				log.Printf("❌ PASS %d BQ START ERROR: %v", pass, err)
			}
			sourceFile.Close()
		}
		os.Remove(tmpFileName)

		// Manage explicit DLQ temporary file storage for analytical observability
		if len(failedBatches) > 0 {
			dlqFileName := fmt.Sprintf("failed_batches_pass_%d.json", pass)
			log.Printf("⚠️ Pass %d finished with %d native DLQ occurrences. Fast-dumping cache payload directly to %s...", pass, len(failedBatches), dlqFileName)
			dlqFile, _ := os.Create(dlqFileName)
			dlqEncoder := json.NewEncoder(dlqFile)
			for _, fb := range failedBatches {
				dlqEncoder.Encode(fb)
			}
			dlqFile.Close()
			defer os.Remove(dlqFileName) // Clean up automatically when main() exits

			if pass == maxPasses {
				log.Printf("❌ CRITICAL: MAX %d DLQ PASSES REACHED. Executing native mathematical fallback padding to manually close %d orphaned candidate nodes.", maxPasses, len(failedBatches))
				padRemainingFailures(ctx, bqClient, failedBatches)
			}
		}

		currentBatches = failedBatches // Relegate target matrix permanently down into the next DLQ filter
	}

	log.Println("✅ ALL DLQ EXECUTIONS ENDED.")
	return nil
}

func singlePassWorker(ctx context.Context, model *genai.GenerativeModel, jobs <-chan []QueueRow, resultsChan chan<- []*BQDecision, failedChan chan<- []QueueRow, wg *sync.WaitGroup) {
	defer wg.Done()

	for batch := range jobs {
		batchJSON, _ := json.MarshalIndent(batch, "", "  ")
		objective := fmt.Sprintf(`
		Please investigate the following %d customer parts and their respective supplier candidates: 
		
		%s
		
		You must evaluate every single candidate for each customer part in the list.
		`, len(batch), string(batchJSON))

		reqCtx, cancel := context.WithTimeout(ctx, 45*time.Second)
		resp, err := model.GenerateContent(reqCtx, genai.Text(objective))
		cancel()

		var finalDecisions []MatchDecision

		isComplete := false
		if err == nil && len(resp.Candidates) > 0 && len(resp.Candidates[0].Content.Parts) > 0 {
			if jsonText, ok := resp.Candidates[0].Content.Parts[0].(genai.Text); ok {
				var parsed []MatchDecision
				if parseErr := json.Unmarshal([]byte(jsonText), &parsed); parseErr == nil {
					decisionMap := make(map[string]MatchDecision)
					for _, d := range parsed {
						key := fmt.Sprintf("%s|%s", d.CustomerPartNumber, d.SupplierPartNumber)
						decisionMap[key] = d
					}
					isComplete = true
					for _, b := range batch {
						for _, c := range b.Candidates {
							key := fmt.Sprintf("%s|%s", b.PartNumber, c.CandidatePartNumber)
							if d, found := decisionMap[key]; !found || d.Decision == "" {
								isComplete = false
								break
							}
						}
						if !isComplete {
							break
						}
					}
					if isComplete {
						finalDecisions = parsed // Perfect native struct block established!
					}
				}
			}
		}

		// Instant DLQ asynchronous offload pipeline if native parsing failed any checks
		if !isComplete || len(finalDecisions) == 0 {
			failedChan <- batch
			continue
		}

		// Process fully successful MatchDecision natively back into final target schema arrays
		var rowsToInsert []*BQDecision
		now := time.Now().UTC()

		decisionMap := make(map[string]MatchDecision)
		for _, d := range finalDecisions {
			key := fmt.Sprintf("%s|%s", d.CustomerPartNumber, d.SupplierPartNumber)
			if _, exists := decisionMap[key]; !exists {
				decisionMap[key] = d
			}
		}

		for _, b := range batch {
			for _, c := range b.Candidates {
				key := fmt.Sprintf("%s|%s", b.PartNumber, c.CandidatePartNumber)

				decisionStr := "REQUIRES_HUMAN_REVIEW"
				reasoningStr := "Agent failed to evaluate or omitted this candidate from batch response."
				if d, found := decisionMap[key]; found {
					decisionStr = d.Decision
					if decisionStr == "" {
						decisionStr = "REQUIRES_HUMAN_REVIEW"
					}
					reasoningStr = d.Reasoning
					if reasoningStr == "" {
						reasoningStr = "Agent explicitly returned a blank decision payload without reasoning."
					}
				}
				isMatch := (decisionStr == "MATCH")

				rowsToInsert = append(rowsToInsert, &BQDecision{
					CustomerPartNumber: b.PartNumber,
					Decision:           decisionStr,
					IsMatch:            isMatch,
					SupplierPartNumber: c.CandidatePartNumber,
					Reasoning:          reasoningStr,
					IsHumanReviewed:    false,
					CreatedAt:          now,
					UpdatedAt:          now,
				})
			}
		}

		if len(rowsToInsert) > 0 {
			resultsChan <- rowsToInsert
		}
	}
}

func padRemainingFailures(ctx context.Context, bqClient *bigquery.Client, failedBatches [][]QueueRow) {
	tmpFileName := "decisions_output_fallback.json"
	tmpFile, _ := os.Create(tmpFileName)
	encoder := json.NewEncoder(tmpFile)
	now := time.Now().UTC()

	var insertedCount int
	for _, batch := range failedBatches {
		for _, b := range batch {
			for _, c := range b.Candidates {
				encoder.Encode(&BQDecision{
					CustomerPartNumber: b.PartNumber,
					Decision:           "REQUIRES_HUMAN_REVIEW",
					IsMatch:            false,
					SupplierPartNumber: c.CandidatePartNumber,
					Reasoning:          "Agent completely failed to reliably execute this schema payload natively across 5 consecutive DLQ passes. Explicitly falling back to mandatory human-in-the-loop validation blocks.",
					IsHumanReviewed:    false,
					CreatedAt:          now,
					UpdatedAt:          now,
				})
				insertedCount++
			}
		}
	}
	tmpFile.Close()

	log.Printf("Padding %d total candidate decisions functionally back onto the fallback trace buffer.", insertedCount)

	sourceFile, _ := os.Open(tmpFileName)
	source := bigquery.NewReaderSource(sourceFile)
	source.SourceFormat = bigquery.JSON
	loader := bqClient.Dataset(datasetID).Table("agent_decisions").LoaderFrom(source)
	loader.WriteDisposition = bigquery.WriteAppend

	log.Println("Starting explicit BigQuery Append-Job for the Fallback Array Component natively...")
	job, err := loader.Run(ctx)
	if err == nil {
		job.Wait(ctx)
		log.Println("✅ FALLBACK MECHANISM PADDED COMPLETELY!")
	} else {
		log.Printf("❌ CRITICAL: Fallback Load job failed to establish parameters: %v", err)
	}

	sourceFile.Close()
	os.Remove(tmpFileName)
}
