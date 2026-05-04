import json
from pathlib import Path

def analyze_matches():
    gold_p = Path("../data/gold/gold_products.json")
    if not gold_p.exists():
        print(f"El archivo Gold no existe en: {gold_p.absolute()}")
        return

    try:
        data = json.loads(gold_p.read_text(encoding="utf-8"))
        products = data.get("gold_products", [])
        
        matches = []
        for p in products:
            variants = p.get("store_variants", [])
            stores = {v["store"] for v in variants}
            if len(stores) >= 2:
                name = p.get("canonical_product", {}).get("name_canonical", "Sin nombre")
                matches.append({
                    "name": name,
                    "stores": list(stores),
                    "score": p.get("confidence_score")
                })
        
        print(f"Productos con matches (>= 2 tiendas): {len(matches)}")
        for p in matches[:20]:
            print(f"- {p['name']} ({', '.join(p['stores'])}) - Score: {p['score']}")
    except Exception as e:
        print(f"Error analizando el archivo: {e}")

if __name__ == "__main__":
    analyze_matches()
