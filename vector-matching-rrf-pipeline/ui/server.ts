import express from "express";
import { createServer as createViteServer } from "vite";
import Database from "better-sqlite3";

const db = new Database("decisions.db");

// Initialize database
db.exec(`
  CREATE TABLE IF NOT EXISTS parts_info (
    part_number TEXT PRIMARY KEY,
    description TEXT,
    manufacturer TEXT,
    category TEXT,
    price REAL
  );

  CREATE TABLE IF NOT EXISTS agent_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_part_number TEXT NOT NULL,
    decision TEXT NOT NULL,
    is_match BOOLEAN NOT NULL,
    supplier_part_number TEXT,
    reasoning TEXT NOT NULL,
    is_human_reviewed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
`);

// Seed data if empty
const count = db.prepare("SELECT COUNT(*) as c FROM agent_decisions").get() as { c: number };
if (count.c === 0) {
  const insertPart = db.prepare("INSERT INTO parts_info (part_number, description, manufacturer, category, price) VALUES (?, ?, ?, ?, ?)");
  const insertDecision = db.prepare("INSERT INTO agent_decisions (customer_part_number, decision, is_match, supplier_part_number, reasoning, is_human_reviewed) VALUES (?, ?, ?, ?, ?, ?)");

  db.transaction(() => {
    // Customer parts
    insertPart.run("CP-1001", "Hex Bolt M8x20mm Stainless", "Acme Corp", "Fasteners", 0.45);
    insertPart.run("CP-1002", "O-Ring Nitrile 10mm ID", "Acme Corp", "Seals", 0.12);
    insertPart.run("CP-2055", "Stepper Motor NEMA 17", "Acme Corp", "Motors", 14.50);
    insertPart.run("CP-3099", "Linear Bearing LM8UU", "Acme Corp", "Bearings", 2.30);
    insertPart.run("CP-4100", "Proximity Sensor Inductive", "Acme Corp", "Sensors", 45.00);
    insertPart.run("CP-5001", "Aluminum Extrusion 2020 1m", "Acme Corp", "Structural", 8.50);
    insertPart.run("CP-6022", "Timing Belt GT2 2m", "Acme Corp", "Belts", 5.20);
    insertPart.run("CP-7011", "Power Supply 24V 15A", "Acme Corp", "Electrical", 35.00);

    // Supplier parts
    insertPart.run("SP-HB-M8-20-SS", "M8 x 20mm Hex Head Bolt, 316 Stainless Steel", "GlobalFast", "Fasteners", 0.48);
    insertPart.run("SP-OR-N-10", "10mm Inner Diameter Nitrile O-Ring", "SealMaster", "Seals", 0.10);
    insertPart.run("SP-SM-17-1.5A", "NEMA 17 Stepper Motor 1.5A 42mm", "MotionPro", "Motors", 13.99);
    insertPart.run("SP-LB-8MM", "8mm Linear Ball Bearing LM8UU", "BearingsRUs", "Bearings", 2.15);
    insertPart.run("SP-PS-IND-12V", "Inductive Proximity Sensor 12V DC NPN", "SenseTech", "Sensors", 42.50);
    insertPart.run("SP-AL-2020-1000", "2020 V-Slot Aluminum Extrusion 1000mm", "StructurAl", "Structural", 9.00);
    insertPart.run("SP-TB-GT2-2000", "GT2 Timing Belt 6mm width 2000mm length", "BeltCo", "Belts", 4.80);
    insertPart.run("SP-PWR-24V-360W", "24V 15A 360W Switching Power Supply", "VoltPower", "Electrical", 32.00);

    // Decisions
    insertDecision.run("CP-1001", "High Confidence Match", 1, "SP-HB-M8-20-SS", "Exact match on dimensions (M8x20mm) and material (Stainless). Embeddings similarity: 0.98.", 0);
    insertDecision.run("CP-1002", "High Confidence Match", 1, "SP-OR-N-10", "Matched material (Nitrile) and inner diameter (10mm). Embeddings similarity: 0.95.", 0);
    insertDecision.run("CP-2055", "Ambiguous Match", 1, "SP-SM-17-1.5A", "NEMA 17 matches, but current rating (1.5A) is not specified in customer part. Embeddings similarity: 0.82.", 0);
    insertDecision.run("CP-3099", "High Confidence Match", 1, "SP-LB-8MM", "LM8UU is a standard part number, exact match. Embeddings similarity: 0.99.", 1);
    insertDecision.run("CP-4100", "Low Confidence Match", 0, "SP-PS-IND-12V", "Both are inductive proximity sensors, but voltage and output type (NPN) are missing from customer spec. Embeddings similarity: 0.65.", 0);
    insertDecision.run("CP-5001", "Ambiguous Match", 1, "SP-AL-2020-1000", "2020 extrusion and 1m length match, but V-Slot vs T-Slot is unspecified. Embeddings similarity: 0.88.", 0);
    insertDecision.run("CP-6022", "High Confidence Match", 1, "SP-TB-GT2-2000", "GT2 and 2m length match. Width is assumed standard 6mm. Embeddings similarity: 0.92.", 0);
    insertDecision.run("CP-7011", "Ambiguous Match", 1, "SP-PWR-24V-360W", "24V 15A matches 360W (24*15=360). Form factor is unknown. Embeddings similarity: 0.85.", 0);
    
    // Add some unmatched ones
    insertDecision.run("CP-8888", "No Match Found", 0, null, "No supplier part found with matching specifications for 'Custom Titanium Bracket'. Highest similarity was 0.32.", 0);
    insertDecision.run("CP-9999", "No Match Found", 0, null, "Insufficient information in customer part description 'Widget A' to find a match.", 0);

  })();
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // API Routes
  app.get("/api/decisions", (req, res) => {
    const { status, search } = req.query;
    
    let query = `
      SELECT 
        d.*,
        cp.description as customer_description,
        cp.manufacturer as customer_manufacturer,
        cp.category as customer_category,
        sp.description as supplier_description,
        sp.manufacturer as supplier_manufacturer,
        sp.category as supplier_category,
        sp.price as supplier_price
      FROM agent_decisions d
      LEFT JOIN parts_info cp ON d.customer_part_number = cp.part_number
      LEFT JOIN parts_info sp ON d.supplier_part_number = sp.part_number
      WHERE 1=1
    `;
    
    const params: any[] = [];

    if (status === 'pending') {
      query += " AND d.is_human_reviewed = 0";
    } else if (status === 'reviewed') {
      query += " AND d.is_human_reviewed = 1";
    }

    if (search) {
      query += " AND (d.customer_part_number LIKE ? OR d.supplier_part_number LIKE ? OR cp.description LIKE ? OR sp.description LIKE ?)";
      const searchTerm = `%${search}%`;
      params.push(searchTerm, searchTerm, searchTerm, searchTerm);
    }

    query += " ORDER BY d.created_at DESC";

    try {
      const rows = db.prepare(query).all(...params);
      res.json(rows);
    } catch (error) {
      console.error(error);
      res.status(500).json({ error: "Database error" });
    }
  });

  app.get("/api/decisions/:id", (req, res) => {
    const { id } = req.params;
    const query = `
      SELECT 
        d.*,
        cp.description as customer_description,
        cp.manufacturer as customer_manufacturer,
        cp.category as customer_category,
        sp.description as supplier_description,
        sp.manufacturer as supplier_manufacturer,
        sp.category as supplier_category,
        sp.price as supplier_price
      FROM agent_decisions d
      LEFT JOIN parts_info cp ON d.customer_part_number = cp.part_number
      LEFT JOIN parts_info sp ON d.supplier_part_number = sp.part_number
      WHERE d.id = ?
    `;
    
    try {
      const row = db.prepare(query).get(id);
      if (row) {
        res.json(row);
      } else {
        res.status(404).json({ error: "Not found" });
      }
    } catch (error) {
      res.status(500).json({ error: "Database error" });
    }
  });

  app.patch("/api/decisions/:id", (req, res) => {
    const { id } = req.params;
    const { is_human_reviewed, is_match, decision } = req.body;
    
    try {
      const current = db.prepare("SELECT * FROM agent_decisions WHERE id = ?").get(id) as any;
      if (!current) {
        return res.status(404).json({ error: "Not found" });
      }

      const newReviewed = is_human_reviewed !== undefined ? is_human_reviewed : current.is_human_reviewed;
      const newMatch = is_match !== undefined ? is_match : current.is_match;
      const newDecision = decision !== undefined ? decision : current.decision;

      db.prepare(`
        UPDATE agent_decisions 
        SET is_human_reviewed = ?, is_match = ?, decision = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `).run(newReviewed ? 1 : 0, newMatch ? 1 : 0, newDecision, id);
      
      const updated = db.prepare("SELECT * FROM agent_decisions WHERE id = ?").get(id);
      res.json(updated);
    } catch (error) {
      console.error(error);
      res.status(500).json({ error: "Database error" });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
