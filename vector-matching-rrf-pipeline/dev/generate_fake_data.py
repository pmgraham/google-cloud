import polars as pl
import random
import uuid

# Set seed for reproducibility
random.seed(42)

# --- Define Canonical Taxonomy ---

# Part Categories & Distribution (Target ~150 parts)
# Fasteners (50%, ~75 parts)
# Bearings (15%, ~23 parts)
# Seals & Gaskets (10%, ~15 parts)
# Electrical (10%, ~15 parts)
# Hydraulic/Pneumatic (10%, ~15 parts)
# Other (5%, ~7 parts)

fastener_types = ['Hex Bolt', 'Socket Head Cap Screw', 'Flat Head Screw', 'Set Screw', 'Hex Nut', 'Lock Nut', 'Flange Nut', 'Flat Washer', 'Lock Washer', 'Threaded Rod']
bearing_types = ['Ball Bearing', 'Roller Bearing', 'Needle Bearing', 'Thrust Bearing', 'Bearing Housing']
seal_types = ['O-Ring', 'Oil Seal', 'Gasket', 'Shaft Seal']
elec_types = ['Connector', 'Terminal', 'Wire', 'Fuse', 'Switch', 'Relay']
hyd_types = ['Fitting', 'Hose', 'Valve', 'Cylinder', 'Quick-Connect']
other_types = ['Filter', 'Adhesive', 'Lubricant', 'Spring', 'Clip']

materials = {
    'Fasteners': [
        ('Stainless Steel', '304', ['SS', 'Stainless', '18-8', 'A2-70', 'Type 304', '304 SS']),
        ('Stainless Steel', '316', ['SS', 'Stainless', '316', 'A4-80', 'Type 316', '316 SS']),
        ('Carbon Steel', 'Grade 5', ['CS', 'Carbon Steel', 'Plain Steel', 'Gr 5', 'Grade 5']),
        ('Carbon Steel', 'Grade 8', ['CS', 'Carbon Steel', 'Black Oxide', 'Gr 8', 'Grade 8']),
        ('Brass', '', ['Brass', 'Yellow Brass'])
    ],
    'General': [
        ('Rubber', 'Buna-N', ['Buna-N', 'Nitrile', 'NBR', 'Rubber']),
        ('Rubber', 'Viton', ['Viton', 'FKM', 'Fluorocarbon']),
        ('Plastic', 'Nylon', ['Nylon', 'Polyamide']),
        ('Steel', 'Chrome', ['Chrome Steel', '52100', 'Bearing Steel']),
        ('Copper', '', ['Copper', 'Bare Copper'])
    ]
}

sizes_metric = ['M4', 'M5', 'M6', 'M8', 'M10', 'M12', 'M16', 'M20']
pitches_metric = ['0.7', '0.8', '1.0', '1.25', '1.5', '1.75', '2.0', '2.5']
lengths_metric = ['10mm', '16mm', '20mm', '25mm', '30mm', '40mm', '50mm', '60mm']

sizes_imp = ['1/4"', '5/16"', '3/8"', '1/2"', '5/8"']
pitches_imp = ['20', '28', '18', '24', '16', '24', '13', '20', '11', '18'] # TPI
lengths_imp = ['1/2"', '3/4"', '1"', '1-1/4"', '1-1/2"', '2"']

standards = {
    'Hex Bolt': [('DIN 933', 'ISO 4017'), ('DIN 931', 'ISO 4014')],
    'Socket Head Cap Screw': [('DIN 912', 'ISO 4762')],
    'Flat Washer': [('DIN 125', 'ISO 7089')]
}

# --- Generate Canonical Parts (Truth Table) ---

def generate_canonical_parts(num_parts):
    parts = []
    for _ in range(num_parts):
        part_id = str(uuid.uuid4())
        
        # Determine category based on distribution
        r = random.random()
        if r < 0.50:
            category = 'Fasteners'
            part_type = random.choice(fastener_types)
        elif r < 0.65:
            category = 'Bearings'
            part_type = random.choice(bearing_types)
        elif r < 0.75:
            category = 'Seals & Gaskets'
            part_type = random.choice(seal_types)
        elif r < 0.85:
            category = 'Electrical'
            part_type = random.choice(elec_types)
        elif r < 0.95:
            category = 'Hydraulic/Pneumatic'
            part_type = random.choice(hyd_types)
        else:
            category = 'Other'
            part_type = random.choice(other_types)

        # Assign material
        mat_options = materials['Fasteners'] if category == 'Fasteners' else materials['General']
        mat_family, mat_grade, mat_aliases = random.choice(mat_options)
        
        # Dimensions & Canonical Desc
        dim = ""
        std_ref = ""
        is_metric = random.choice([True, False])
        
        if category == 'Fasteners' and part_type in ['Hex Bolt', 'Socket Head Cap Screw', 'Flat Head Screw', 'Set Screw']:
            if is_metric:
                size = random.choice(sizes_metric)
                pitch = random.choice(pitches_metric)
                length = random.choice(lengths_metric)
                dim = f"{size}x{pitch}x{length}"
            else:
                size = random.choice(sizes_imp)
                tpi = random.choice(pitches_imp)
                length = random.choice(lengths_imp)
                dim = f"{size}-{tpi} x {length}"
            
            if part_type in standards:
                std_ref = f" ({random.choice(standards[part_type])[0]})"
                
            canonical_desc = f"{mat_family} {part_type} {dim}{std_ref}"
        
        elif category == 'Bearings':
            series = random.choice(['6200', '6201', '6202', '6203', '6204', '6205'])
            seal_type = random.choice(['ZZ', '2RS', 'Open'])
            dim = f"Series {series}-{seal_type}"
            canonical_desc = f"{part_type} {dim}"
            
        elif category == 'Seals & Gaskets' and part_type == 'O-Ring':
            id_mm = random.randint(10, 50)
            cs_mm = random.choice([1.5, 2.0, 2.5, 3.0])
            dim = f"{id_mm}mm ID x {cs_mm}mm CS"
            canonical_desc = f"{mat_grade} {part_type} {dim}"
            
        else:
            canonical_desc = f"{mat_family} {part_type} Standard Configuration"

        parts.append({
            'canonical_part_id': part_id,
            'canonical_description': canonical_desc,
            'category': category,
            'part_type': part_type,
            'mat_family': mat_family,
            'mat_grade': mat_grade,
            'mat_aliases': mat_aliases,
            'is_metric': is_metric,
            'dim': dim
        })
    return parts

# Generate ~150 canonical parts
canonical_parts = generate_canonical_parts(150)

# --- Source Allocation ---
# Target:
# ~100 parts in 2-3 sources (including Customer + >=1 supplier)
# ~30 parts in 4-5 sources
# ~20 parts Customer only, ~20 parts Supplier only (we'll adjust generation for ~190 total to hit these)

sources = ['Customer', 'Source1', 'Source2', 'Source3', 'Source4']
truth_table = []

# Customer must have ~150 parts that match somewhere, ~50 that match nowhere
# Source distributions: Source1 (~250), Source2 (~250), Source3 (~150), Source4 (~150)
# We need to generate *more* canonical parts just for specific sources to meet these counts.

# 1. 30 parts in all 5 sources
for i in range(30):
    p = canonical_parts[i]
    for s in sources:
        truth_table.append({'canonical_part_id': p['canonical_part_id'], 'source': s, 'part_data': p})

# 2. 100 parts in Customer + 1-2 suppliers
for i in range(30, 130):
    p = canonical_parts[i]
    supplier_pool = ['Source1', 'Source2', 'Source3', 'Source4']
    num_suppliers = random.choice([1, 2])
    selected_suppliers = random.sample(supplier_pool, num_suppliers)
    
    truth_table.append({'canonical_part_id': p['canonical_part_id'], 'source': 'Customer', 'part_data': p})
    for s in selected_suppliers:
        truth_table.append({'canonical_part_id': p['canonical_part_id'], 'source': s, 'part_data': p})

# 3. 50 parts Customer ONLY (No match)
customer_only_parts = generate_canonical_parts(50)
for p in customer_only_parts:
    truth_table.append({'canonical_part_id': p['canonical_part_id'], 'source': 'Customer', 'part_data': p})

# 4. Fill up suppliers with supplier-only parts or supplier-to-supplier matches (No Customer)
# Let's add ~120 parts scattered among suppliers to pump their numbers up
supplier_only_parts = generate_canonical_parts(120)
for p in supplier_only_parts:
    supplier_pool = ['Source1', 'Source2', 'Source3', 'Source4']
    num_suppliers = random.choice([1, 2, 3])
    selected_suppliers = random.sample(supplier_pool, num_suppliers)
    for s in selected_suppliers:
        truth_table.append({'canonical_part_id': p['canonical_part_id'], 'source': s, 'part_data': p})

# --- Generate Source-Specific Variations ---

def format_abbreviation(s):
    abbr_map = {'Hex Bolt': 'HB', 'Socket Head Cap Screw': 'SHCS', 'Stainless Steel': 'SS', 'Carbon Steel': 'CS'}
    for k, v in abbr_map.items():
        s = s.replace(k, v)
    return s

def get_source_data(record, counter):
    source = record['source']
    p = record['part_data']
    
    part_number = ""
    part_description = ""
    material = None
    dimensions = None
    category = None
    
    mat_alias = random.choice(p['mat_aliases']) if p['mat_aliases'] else p['mat_family']
    
    # 1. Customer (Terse, separate fields, internal PN)
    if source == 'Customer':
        part_number = f"ERP-{1000000 + counter}"
        desc = f"{p['part_type']} {p['dim']}".replace(' x ', 'x').replace('-', '')
        part_description = format_abbreviation(desc).upper()
        material = mat_alias.upper()
        dimensions = p['dim'].replace(' x ', 'x').upper()
        category = p['category'].upper()

    # 2. Source1 (Fastenal-style: FAS-PN, moderate desc, heavy abbrev)
    elif source == 'Source1':
        prefix = format_abbreviation(p['part_type']).upper().replace(' ', '')
        part_number = f"FAS-{prefix}-{counter:05d}"
        part_description = f"{format_abbreviation(p['part_type'])} {p['dim']} {mat_alias}".upper()
        material = mat_alias
        dimensions = p['dim']
        category = p['category']

    # 3. Source2 (McMaster-style: Numeric PN, verbose desc, embedded attributes)
    elif source == 'Source2':
        part_number = f"{random.randint(90000, 99999)}A{random.randint(100, 999)}"
        part_description = f"{mat_alias} {p['part_type']}, {p['dim'].replace('x', ' Thread Size, ')} Length"
        if p['category'] == 'Fasteners' and p['part_type'] in standards:
            part_description += f", meets {random.choice(standards[p['part_type']])[0]} / {random.choice(standards[p['part_type']])[1]}"
        # Nullify specific fields as per specs
        if random.random() < 0.7:
            material = None
        if random.random() < 0.7:
            dimensions = None

    # 4. Source3 (Legacy MRO: Short codes, messy, nulls)
    elif source == 'Source3':
        prefix = format_abbreviation(p['part_type']).upper().replace(' ', '')
        part_number = f"{prefix}-{counter}"
        
        # Introduce sloppiness
        type_str = format_abbreviation(p['part_type']).lower()
        if random.random() < 0.2:
            type_str = type_str.replace('bolt', 'blt').replace('screw', 'scrw').replace('stainless', 'stainles')
            
        dim_str = p['dim'].lower().replace('x', ' ').replace('-', ' ').replace('  ', ' ')
        part_description = f"{mat_alias.lower()} {type_str} {dim_str}"
        
        material = None
        dimensions = None
        if random.random() < 0.5:
            category = None

    # 5. Source4 (International: European standard focus, metric only)
    elif source == 'Source4':
        std = ""
        if p['category'] == 'Fasteners' and p['part_type'] in standards:
            std = random.choice(standards[p['part_type']])[0] + "-"
            
        part_number = f"{std}{counter:05d}"
        
        # Force metric conversion visually if imperial (for variation purposes)
        dim_str = p['dim']
        if not p['is_metric'] and 'x' in p['dim']:
             # fake conversion for variation
             dim_str = p['dim'].replace('1/4"', '6.35mm').replace('3/8"', '9.5mm').replace('1/2"', '12.7mm')
             
        part_description = f"{p['part_type']} {std} {dim_str} {mat_alias}"
        material = mat_alias
        dimensions = dim_str
        category = "European " + p['category']

    return {
        'canonical_part_id': p['canonical_part_id'],
        'canonical_description': p['canonical_description'],
        'source': source,
        'part_number': part_number,
        'part_description': part_description,
        'material': material,
        'dimensions': dimensions,
        'category': category
    }

final_records = []
counter_map = {s: 1 for s in sources}

for r in truth_table:
    res = get_source_data(r, counter_map[r['source']])
    final_records.append(res)
    counter_map[r['source']] += 1

# --- Convert to Polars and Save ---

df = pl.DataFrame(final_records)

# 1. Save Truth Table (Answer Key)
truth_df = df.select([
    'canonical_part_id', 
    'canonical_description', 
    'source', 
    'part_number'
])
truth_df.write_csv('data/truth_table.csv')

# 2. Save Source Tables
for s in sources:
    source_df = df.filter(pl.col("source") == s).select([
        'part_number',
        'part_description',
        'material',
        'dimensions',
        'category'
    ])
    source_df.write_csv(f'data/raw_{s.lower()}_parts.csv')

print("Synthetic data generation complete. Files written to data/ directory.")
for s in sources:
     print(f" - raw_{s.lower()}_parts.csv: {df.filter(pl.col('source') == s).height} rows")
print(f" - truth_table.csv: {truth_df.height} rows")
