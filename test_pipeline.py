import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, save_tracked_product, save_price_records, save_ai_recommendation, get_tracked_products
from core.scraper import PriceScraper
from core.advisor import AdvisorAI

def test_pipeline():
    init_db()
    print("[1] Banco de dados SQLite inicializado.")
    
    query = "Monitor Gamer 144hz"
    intent = "Melhor tempo de resposta para FPS até 900 reais"
    
    offers = PriceScraper.search_mercadolivre(query, limit=5)
    print(f"[2] Scraper obteve {len(offers)} ofertas.")
    
    pid = save_tracked_product(query, target_price=850.0, user_intent=intent)
    save_price_records(offers, product_id=pid)
    print(f"[3] Registros persistidos para produto ID: {pid}")
    
    rec = AdvisorAI.analyze_offers(query, offers, intent)
    print(f"[4] Decisão da IA: {rec['verdict']}")
    print(f"    Melhor escolha: {rec['best_pick']['title']} (R$ {rec['best_pick']['price']})")
    print(f"    Resumo: {rec['summary']}")
    
    prods = get_tracked_products()
    print(f"[5] Total de produtos rastreados: {len(prods)}")
    print("[✓] Pipeline completo validado com sucesso!")

if __name__ == "__main__":
    test_pipeline()
