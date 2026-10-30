import http.server
import socketserver
import json
import urllib.parse
import os
import sys

# Adicionar pasta raiz ao path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from core.database import init_db, save_tracked_product, save_price_records, save_ai_recommendation, get_tracked_products, get_product_details
from core.scraper import PriceScraper
from core.advisor import AdvisorAI

PORT = 5050

class PrecoCertoHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "/index.html":
            self.serve_html()
        elif path == "/api/products":
            products = get_tracked_products()
            self.send_json(products)
        elif path.startswith("/api/product/"):
            try:
                prod_id = int(path.split("/")[-1])
                details = get_product_details(prod_id)
                self.send_json(details)
            except Exception as e:
                self.send_json({"error": str(e)}, status=400)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/api/search":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
            
            product_name = data.get("name", "").strip()
            user_intent = data.get("intent", "").strip()
            target_price = float(data["target_price"]) if data.get("target_price") else None
            
            if not product_name:
                self.send_json({"error": "Nome do produto é obrigatório"}, status=400)
                return
                
            # 1. Salvar rastreamento
            product_id = save_tracked_product(product_name, target_price, user_intent)
            
            # 2. Executar Scraper de ofertas em tempo real
            offers = PriceScraper.search_mercadolivre(product_name, limit=10)
            save_price_records(offers, product_id=product_id)
            
            # 3. Executar o Agente de Decisão de Compra com IA
            decision = AdvisorAI.analyze_offers(product_name, offers, user_intent)
            save_ai_recommendation(
                product_id=product_id,
                verdict=decision["verdict"],
                best_pick=decision["best_pick"],
                summary=decision["summary"],
                pros_cons_json=json.dumps({
                    "analysis_points": decision.get("analysis_points", []),
                    "savings_tip": decision.get("savings_tip", "")
                }, ensure_ascii=False)
            )
            
            details = get_product_details(product_id)
            self.send_json(details)
        else:
            self.send_json({"error": "Rota não encontrada"}, status=404)

    def send_json(self, data, status=200):
        response_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response_bytes)

    def serve_html(self):
        template_path = os.path.join(PROJECT_ROOT, "web", "templates", "index.html")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                html = f.read()
        else:
            html = "<h1>Preço Certo AI</h1>"
        html_bytes = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

def run_server():
    init_db()
    with socketserver.TCPServer(("", PORT), PrecoCertoHandler) as httpd:
        print(f"[*] Preço Certo AI rodando em http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor finalizado.")

if __name__ == "__main__":
    run_server()
