import json
from pathlib import Path

def analyze_triple_matches():
    # Usar ruta relativa correcta si se ejecuta desde la carpeta 'scrapers'
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"
    gold_p = DATA_DIR / "gold" / "gold_products.json"
    if not gold_p.exists():
        print(f"El archivo Gold no existe en: {gold_p.absolute()}")
        return

    try:
        data = json.loads(gold_p.read_text(encoding="utf-8"))
        # En el Sprint 3, la llave es 'gold_products'
        products = data.get("gold_products", [])
        
        triple_matches = []
        for p in products:
            # En el Sprint 3, la llave es 'store_variants'
            variants = p.get("store_variants", [])
            stores = {v["store"] for v in variants}
            if len(stores) >= 3:
                # El nombre está en canonical_product -> name_canonical
                name = p.get("canonical_product", {}).get("name_canonical", "Sin nombre")
                triple_matches.append({
                    "name": name,
                    "stores": list(stores),
                    "score": p.get("confidence_score")
                })
        
        print(f"Total de productos encontrados en las 3 tiendas: {len(triple_matches)}")
        if triple_matches:
            print("\nEjemplos:")
            for m in triple_matches[:10]:
                print(f"- {m['name']} (Tiendas: {', '.join(m['stores'])}) - Score: {m['score']}")
    except Exception as e:
        print(f"Error analizando el archivo: {e}")

if __name__ == "__main__":
    analyze_triple_matches()
