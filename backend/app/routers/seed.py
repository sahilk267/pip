"""Comprehensive seed endpoint — vendors, products, leads + all feature data."""
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, crud, schemas
from ..models_extended import (
    PriceHistory, PriceBenchmark, SupplierScore, SupplierRatingHistory,
    Invoice, InvoiceItem, DiscountTier, CostOpportunity, RFQTemplate, RFQTemplateItem,
)
from ..services import price_trends as pt_svc, supplier_scoring as ss_svc

router = APIRouter()

# ─── Master data ─────────────────────────────────────────────────────────────

VENDORS = [
    {"name": "Apex Electronics Supply",       "industry": "Electronics",    "category": "Electronics",    "country": "USA",     "email": "ops@apexelectronics.com"},
    {"name": "GlobalTech Components",         "industry": "Electronics",    "category": "Electronics",    "country": "China",   "email": "sales@globaltech.cn"},
    {"name": "NovaParts Manufacturing",       "industry": "Manufacturing",  "category": "Manufacturing",  "country": "Germany", "email": "info@novaparts.de"},
    {"name": "PrimeMetal Works",              "industry": "Manufacturing",  "category": "Manufacturing",  "country": "India",   "email": "sales@primemetal.in"},
    {"name": "BlueRaw Materials Ltd",         "industry": "Raw Materials",  "category": "Raw Materials",  "country": "Brazil",  "email": "ops@blueraw.br"},
    {"name": "OceanMine Resources",           "industry": "Raw Materials",  "category": "Raw Materials",  "country": "Australia","email": "contact@oceanmine.au"},
    {"name": "FastFreight Logistics",         "industry": "Logistics",      "category": "Logistics",      "country": "USA",     "email": "dispatch@fastfreight.com"},
    {"name": "AirCargo Express",              "industry": "Logistics",      "category": "Logistics",      "country": "Singapore","email": "ops@aircargo.sg"},
    {"name": "CloudSoft Solutions",           "industry": "Software",       "category": "Software",       "country": "USA",     "email": "sales@cloudsoft.io"},
    {"name": "DevPlatform Inc",               "industry": "Software",       "category": "Software",       "country": "India",   "email": "hello@devplatform.in"},
    {"name": "ProChem Industries",            "industry": "Chemicals",      "category": "Chemicals",      "country": "Germany", "email": "sales@prochem.de"},
    {"name": "SafePack Packaging Co",         "industry": "Packaging",      "category": "Packaging",      "country": "Mexico",  "email": "contact@safepack.mx"},
    {"name": "QualityServe Consulting",       "industry": "Services",       "category": "Services",       "country": "UK",      "email": "info@qualityserve.co.uk"},
    {"name": "TechBridge Systems",            "industry": "Electronics",    "category": "Electronics",    "country": "Taiwan",  "email": "sales@techbridge.tw"},
    {"name": "MegaForge Industrial",          "industry": "Manufacturing",  "category": "Manufacturing",  "country": "China",   "email": "ops@megaforge.cn"},
]

PRODUCTS = [
    {"name": "Microcontroller Unit ATmega328", "sku": "MCU-ATM328",  "category": "Electronics",   "price": "4.50"},
    {"name": "OLED Display Module 128x64",     "sku": "DISP-OL128",  "category": "Electronics",   "price": "12.99"},
    {"name": "Industrial Power Supply 24V",    "sku": "PSU-IND24V",  "category": "Electronics",   "price": "89.00"},
    {"name": "CNC Precision Part Set",         "sku": "CNC-PRC001",  "category": "Manufacturing", "price": "340.00"},
    {"name": "Aluminum Extrusion Profile 80/20","sku": "ALU-EXT80",  "category": "Manufacturing", "price": "28.50"},
    {"name": "Copper Wire 22 AWG (100m)",      "sku": "CUW-22AWG",   "category": "Raw Materials", "price": "18.75"},
    {"name": "Carbon Fiber Sheet 2mm",         "sku": "CF-SHT2MM",   "category": "Raw Materials", "price": "65.00"},
    {"name": "Air Freight Rate (per kg)",      "sku": "LOG-AIRKG",   "category": "Logistics",     "price": "6.20"},
    {"name": "Sea Freight FCL 20ft",           "sku": "LOG-FCL20",   "category": "Logistics",     "price": "1200.00"},
    {"name": "Enterprise SaaS License Annual", "sku": "SW-ENT-ANN",  "category": "Software",      "price": "2400.00"},
    {"name": "API Platform Access Monthly",    "sku": "SW-API-MO",   "category": "Software",      "price": "299.00"},
    {"name": "Industrial Solvent IPA 99%",     "sku": "CHE-IPA99",   "category": "Chemicals",     "price": "42.00"},
    {"name": "Corrugated Box 30x20x15 cm",     "sku": "PKG-CB3020",  "category": "Packaging",     "price": "0.85"},
    {"name": "QC Inspection Service (per lot)", "sku": "SVC-QCI001", "category": "Services",      "price": "450.00"},
    {"name": "PCB Assembly Run (100 units)",   "sku": "MFG-PCBA100", "category": "Electronics",   "price": "1240.00"},
]

LEADS = [
    {"company": "InnovateTech Corp",      "contact_name": "James Wilson",    "email": "james@innovatetech.com",   "stage": "qualified",  "segment": "enterprise", "score": 82},
    {"company": "QuickBuy Retail",        "contact_name": "Sara Chen",       "email": "sara@quickbuy.io",         "stage": "proposal",   "segment": "smb",        "score": 64},
    {"company": "BuildRight Ltd",         "contact_name": "Rahul Patel",     "email": "rahul@buildright.co",      "stage": "discovery",  "segment": "mid_market", "score": 51},
    {"company": "NovaMed Devices",        "contact_name": "Emily Torres",    "email": "emily@novamed.com",        "stage": "negotiation","segment": "enterprise", "score": 91},
    {"company": "EcoForce Industries",    "contact_name": "Liu Wei",         "email": "liu@ecoforce.cn",          "stage": "closed_won", "segment": "enterprise", "score": 95},
    {"company": "SpeedParts Online",      "contact_name": "Alex Brooks",     "email": "alex@speedparts.net",      "stage": "lead",       "segment": "smb",        "score": 34},
    {"company": "Meridian Logistics",     "contact_name": "Paula Kim",       "email": "paula@meridianlog.com",    "stage": "qualified",  "segment": "mid_market", "score": 73},
    {"company": "Alpine Manufacturing",   "contact_name": "Stefan Bauer",    "email": "stefan@alpineman.de",      "stage": "proposal",   "segment": "enterprise", "score": 88},
    {"company": "SkyBridge Imports",      "contact_name": "Maria Ruiz",      "email": "maria@skybridge.es",       "stage": "discovery",  "segment": "smb",        "score": 47},
    {"company": "PeakSupply Chain",       "contact_name": "Tom Nakamura",    "email": "tom@peaksupply.jp",        "stage": "negotiation","segment": "mid_market", "score": 79},
]


# ─── Category price ranges for realistic seed data ────────────────────────────

CAT_RANGES = {
    "Electronics":   (10.0,   800.0),
    "Manufacturing": (100.0, 5000.0),
    "Raw Materials": (5.0,    500.0),
    "Logistics":     (20.0,  2000.0),
    "Software":      (99.0, 12000.0),
    "Services":      (50.0,  5000.0),
    "Chemicals":     (15.0,  1000.0),
    "Packaging":     (0.50,   200.0),
    "uncategorized": (20.0,  1000.0),
}

CAT_PRODUCTS = {
    "Electronics":   ["Microcontrollers", "OLED Displays", "Power Modules", "Sensor Arrays", "PCB Assemblies"],
    "Manufacturing": ["CNC Parts", "Steel Castings", "Aluminum Extrusions", "Tooling Sets", "Precision Gears"],
    "Raw Materials": ["Copper Wire", "Polymer Resin", "Steel Sheets", "Aluminum Alloy", "Carbon Fiber"],
    "Logistics":     ["Air Freight/kg", "Sea Freight CBM", "Last-Mile Delivery", "Warehousing sqft"],
    "Software":      ["Enterprise License", "SaaS Monthly", "Support Plan", "API Access"],
    "Services":      ["QC Inspection", "Engineering Consulting", "Installation", "Training Hours"],
    "Chemicals":     ["Industrial Solvents", "Adhesives", "Lubricants", "Coatings"],
    "Packaging":     ["Cardboard Boxes", "Bubble Wrap", "Foam Inserts", "Pallets"],
    "uncategorized": ["General Supply", "Mixed Goods", "Standard Parts"],
}


@router.post('/api/v1/seed-all')
def seed_all(db: Session = Depends(get_db)) -> dict:
    """
    One-shot seed that populates:
    - 15 vendors  (deduplicated)
    - 15 products (deduplicated)
    - 10 leads
    - Price history (~250 records) + benchmarks
    - Supplier scores for every vendor
    - Discount tiers + cost opportunities
    - 10 sample invoices
    Returns a summary of everything created.
    """
    summary: dict = {}
    now = datetime.now(timezone.utc)

    # ── 1. Vendors ────────────────────────────────────────────────────────────
    v_created = v_skipped = 0
    vendor_objs: list[models.Vendor] = []

    for v in VENDORS:
        schema = schemas.VendorCreate(
            name=v["name"],
            source="seed",
            contact_email=v.get("email"),
            industry=v.get("industry"),
            vendor_metadata={"country": v.get("country", "")},
        )
        obj, created = crud.create_vendor(db, schema)
        # Ensure category is set (crud.create_vendor doesn't set it)
        if obj.category == "uncategorized" and v.get("category"):
            obj.category = v["category"]
            db.add(obj)
        vendor_objs.append(obj)
        if created:
            v_created += 1
        else:
            v_skipped += 1

    db.commit()
    # Refresh objects to get IDs
    vendor_objs = db.query(models.Vendor).all()
    summary["vendors"] = {"created": v_created, "skipped": v_skipped, "total": len(vendor_objs)}

    # ── 2. Products ───────────────────────────────────────────────────────────
    p_created = p_skipped = 0
    for i, p in enumerate(PRODUCTS):
        # Assign vendor by matching category
        matching = [v for v in vendor_objs if v.category == p.get("category", "uncategorized")]
        vendor_id = (matching[i % len(matching)].id if matching else vendor_objs[i % len(vendor_objs)].id)

        schema = schemas.ProductCreate(
            name=p["name"],
            sku=p.get("sku"),
            vendor_id=vendor_id,
            price=p.get("price"),
            attributes={"category": p.get("category", "uncategorized")},
        )
        _, created = crud.create_product(db, schema)
        if created:
            # Set category on the product
            prod = db.query(models.Product).filter(models.Product.sku == p["sku"]).first()
            if prod:
                prod.category = p.get("category", "uncategorized")
                db.add(prod)
            p_created += 1
        else:
            p_skipped += 1

    db.commit()
    summary["products"] = {"created": p_created, "skipped": p_skipped}

    # ── 3. Leads ──────────────────────────────────────────────────────────────
    l_created = 0
    for lead in LEADS:
        exists = db.query(models.Lead).filter(models.Lead.email == lead["email"]).first()
        if not exists:
            db.add(models.Lead(
                company=lead["company"],
                full_name=lead["contact_name"],
                email=lead["email"],
                stage=lead["stage"],
                segment=lead.get("segment", "smb"),
                lead_score=lead.get("score", 50),
                source="seed",
                attribution_channel="seed",
                marketing_consent="unknown",
            ))
            l_created += 1
    db.commit()
    summary["leads"] = {"created": l_created}

    # ── 4. Price history ──────────────────────────────────────────────────────
    ph_created = 0
    categories = list(CAT_RANGES.keys())

    # Skip if already seeded
    existing_ph = db.query(PriceHistory).count()
    if existing_ph < 20:
        for vendor in vendor_objs[:15]:
            primary_cat = vendor.category if vendor.category in CAT_RANGES else "uncategorized"
            secondary = random.sample([c for c in categories if c != primary_cat], min(3, len(categories) - 1))
            vendor_cats = [(primary_cat, 9)] + [(c, 3) for c in secondary]

            for cat, n in vendor_cats:
                lo, hi = CAT_RANGES[cat]
                base = random.uniform(lo, hi)
                prods = CAT_PRODUCTS.get(cat, ["Generic Product"])

                for _ in range(n):
                    days_ago = random.randint(1, 90)
                    price = round(base * random.uniform(0.92, 1.08), 2)
                    db.add(PriceHistory(
                        vendor_id=vendor.id,
                        product_name=random.choice(prods),
                        unit_price=price,
                        category=cat,
                        quantity=random.choice([10, 25, 50, 100, 250, 500]),
                        source="historical",
                        recorded_at=now - timedelta(days=days_ago),
                    ))
                    ph_created += 1

        db.commit()

        # Refresh benchmarks
        for cat in categories:
            try:
                pt_svc.calculate_benchmark(db, cat)
            except Exception:
                pass

    summary["price_history"] = {"records_created": ph_created, "skipped_if_zero": existing_ph >= 20}

    # ── 5. Supplier scores ────────────────────────────────────────────────────
    scored = failed = 0
    for vendor in vendor_objs:
        try:
            ss_svc.calculate_supplier_score(db, vendor.id)
            scored += 1
        except Exception:
            failed += 1
    summary["supplier_scores"] = {"scored": scored, "failed": failed}

    # ── 6. Discount tiers ─────────────────────────────────────────────────────
    tiers_created = 0
    cat_list = ["Electronics", "Manufacturing", "Raw Materials", "Logistics", "Software", "Packaging"]
    cat_prices = {
        "Electronics": (40.0, 350.0), "Manufacturing": (120.0, 3000.0),
        "Raw Materials": (7.0, 380.0), "Logistics": (35.0, 1500.0),
        "Software": (79.0, 8000.0), "Packaging": (0.40, 160.0),
    }
    for i, vendor in enumerate(vendor_objs[:12]):
        vendor_cats = [cat_list[i % len(cat_list)], cat_list[(i + 2) % len(cat_list)]]
        for cat in vendor_cats:
            lo, hi = cat_prices.get(cat, (30.0, 500.0))
            base = round(random.uniform(lo, hi), 2)
            for min_q, max_q, disc in [(10, 499, 0), (500, 1999, 10), (2000, None, 22)]:
                exists = db.query(DiscountTier).filter(
                    DiscountTier.vendor_id == vendor.id,
                    DiscountTier.product_category == cat,
                    DiscountTier.min_quantity == min_q,
                ).first()
                if not exists:
                    price = round(base * (1 - disc / 100), 2)
                    db.add(DiscountTier(
                        vendor_id=vendor.id, product_category=cat,
                        min_quantity=min_q, max_quantity=max_q,
                        unit_price=price, discount_percentage=disc,
                        notes=f"Auto-seeded tier for {cat}",
                    ))
                    tiers_created += 1
    db.commit()
    summary["discount_tiers"] = {"created": tiers_created}

    # ── 7. Cost opportunities ─────────────────────────────────────────────────
    opp_templates = [
        ("Consolidate Electronics Orders Q3",   "Electronics",   "consolidation",       85000, 12750),
        ("Switch to tier-2 Raw Materials vendor","Raw Materials", "alternative_vendor",  42000,  8400),
        ("Volume discount: Manufacturing Q4",    "Manufacturing", "bulk_discount",      220000, 33000),
        ("Logistics network optimization",       "Logistics",     "consolidation",       65000,  9750),
        ("Software license renegotiation",       "Software",      "alternative_vendor", 120000, 24000),
        ("Packaging bulk purchase Q1",           "Packaging",     "bulk_discount",       18000,  2700),
    ]
    opps_created = 0
    for title, cat, otype, cost, savings in opp_templates:
        exists = db.query(CostOpportunity).filter(CostOpportunity.title == title).first()
        if not exists:
            db.add(CostOpportunity(
                title=title, category=cat, opportunity_type=otype,
                current_cost=cost, potential_savings=savings,
                savings_percentage=round(savings / cost * 100, 1),
                recommended_action=f"Review {cat} spend and negotiate with top vendors",
                affected_vendors=[v.id for v in vendor_objs[:3]],
                status=random.choice(["identified", "identified", "approved"]),
            ))
            opps_created += 1
    db.commit()
    summary["cost_opportunities"] = {"created": opps_created}

    # ── 8. Sample invoices ────────────────────────────────────────────────────
    inv_count = db.query(Invoice).count()
    inv_created = 0
    if inv_count < 8 and vendor_objs:
        line_items = [
            ("Bulk Electronics Supply Q2",   200,   45.50),
            ("Manufacturing Parts Order",     50,  320.00),
            ("Raw Materials Delivery",      1000,    8.75),
            ("Logistics Services April",      30,  250.00),
            ("Software Licenses Annual",       5, 1200.00),
            ("Packaging Materials Bulk",    5000,    0.85),
            ("Engineering Consulting Hrs",    40,  180.00),
            ("Chemical Compounds Batch",     100,   55.00),
            ("PCB Assembly Run",             500,   12.40),
            ("QC Inspection Service",          1, 3500.00),
        ]
        statuses = ["paid", "paid", "sent", "sent", "draft", "draft", "paid", "sent", "draft", "paid"]
        terms_list = ["Net 15", "Net 30", "Net 30", "Net 60"]
        days_map = {"Net 15": 15, "Net 30": 30, "Net 60": 60}

        for i, vendor in enumerate(vendor_objs[:10]):
            status = statuses[i]
            terms = random.choice(terms_list)
            inv_date = now - timedelta(days=random.randint(5, 60))
            due_date = inv_date + timedelta(days=days_map[terms])
            desc, qty, unit = line_items[i]
            total = round(qty * unit, 2)
            count = db.query(Invoice).count()
            inv_num = f"INV-{inv_date.strftime('%Y%m%d')}-{count + 1:04d}"

            inv = Invoice(
                invoice_number=inv_num, vendor_id=vendor.id,
                po_number=f"PO-{2025000 + i + 1}", total_amount=total,
                currency="USD", status=status,
                invoice_date=inv_date, due_date=due_date,
                paid_date=inv_date + timedelta(days=random.randint(3, 14)) if status == "paid" else None,
                payment_terms=terms, notes=f"Seeded sample invoice for {vendor.name}",
                created_by="seed",
            )
            db.add(inv)
            db.flush()
            db.add(InvoiceItem(
                invoice_id=inv.id, description=desc,
                quantity=qty, unit_price=unit, total_price=total,
            ))
            inv_created += 1

        db.commit()
    summary["invoices"] = {"created": inv_created, "skipped_if_zero": inv_count >= 8}

    # ── 9. RFQ Templates ──────────────────────────────────────────────────────
    tmpl_count = db.query(RFQTemplate).count()
    tmpl_created = 0
    if tmpl_count < 4:
        TEMPLATES = [
            {
                "name": "Electronics Quarterly Restock",
                "category": "Electronics",
                "description": "Standard quarterly reorder for all electronic components",
                "items": [
                    {"product_name": "Microcontrollers (STM32)", "quantity": 500, "target_price": 8.50, "lead_time_days": 21},
                    {"product_name": "PCB Assemblies", "quantity": 200, "target_price": 45.00, "lead_time_days": 30},
                    {"product_name": "Sensor Arrays", "quantity": 100, "target_price": 120.00, "lead_time_days": 14},
                    {"product_name": "Power Modules", "quantity": 150, "target_price": 35.00, "lead_time_days": 7},
                ],
            },
            {
                "name": "Manufacturing Supplies Bundle",
                "category": "Manufacturing",
                "description": "Monthly manufacturing raw inputs and tooling",
                "items": [
                    {"product_name": "Steel Rods (Grade A)", "quantity": 2000, "target_price": 3.20, "lead_time_days": 10},
                    {"product_name": "Precision Bolts M8", "quantity": 10000, "target_price": 0.15, "lead_time_days": 5},
                    {"product_name": "Industrial Lubricant", "quantity": 50, "target_price": 85.00, "lead_time_days": 7},
                ],
            },
            {
                "name": "Software & Cloud Licenses",
                "category": "Software",
                "description": "Annual software license renewal batch",
                "items": [
                    {"product_name": "ERP Platform License", "quantity": 25, "target_price": 1200.00, "lead_time_days": 3},
                    {"product_name": "Analytics Suite", "quantity": 10, "target_price": 800.00, "lead_time_days": 1},
                    {"product_name": "Security Monitoring Tool", "quantity": 5, "target_price": 2000.00, "lead_time_days": 1},
                ],
            },
            {
                "name": "Logistics & Packaging Bundle",
                "category": "Logistics",
                "description": "Shipping and packaging materials for Q3",
                "items": [
                    {"product_name": "Corrugated Boxes (Large)", "quantity": 5000, "target_price": 1.20, "lead_time_days": 5},
                    {"product_name": "Bubble Wrap Rolls", "quantity": 200, "target_price": 18.00, "lead_time_days": 3},
                    {"product_name": "Freight Services (FTL)", "quantity": 10, "target_price": 3500.00, "lead_time_days": 14},
                ],
            },
        ]
        for t in TEMPLATES:
            tmpl = RFQTemplate(
                name=t["name"], category=t["category"],
                description=t["description"], created_by="seed", is_public=True,
            )
            db.add(tmpl)
            db.flush()
            for it in t["items"]:
                db.add(RFQTemplateItem(
                    template_id=tmpl.id,
                    product_name=it["product_name"],
                    quantity=it["quantity"],
                    target_price=it.get("target_price"),
                    lead_time_days=it.get("lead_time_days"),
                    notes="Seeded sample item",
                ))
            tmpl_created += 1
        db.commit()
    summary["rfq_templates"] = {"created": tmpl_created, "skipped_if_existing": tmpl_count >= 4}

    summary["status"] = "ok"
    summary["seeded_at"] = now.isoformat()
    return summary
