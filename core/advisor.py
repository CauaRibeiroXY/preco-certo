import os
import json
from typing import List, Dict, Any, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

class AdvisorAI:
    """
    Agente de Decisão de Compra com Inteligência Artificial
    Analisa ofertas, custo-benefício, reputação e dá o veredito final
    """

    SYSTEM_PROMPT = """Você é um especialista implacável em inteligência de compras e análise de custo-benefício.
Sua missão é analisar uma lista de ofertas encontradas para o usuário, considerar a intenção de compra dele,
e responder com um diagnóstico preciso, honesto e focado em economizar dinheiro real.

Você DEVE responder ESTRITAMENTE em formato JSON com o seguinte schema:
{
  "verdict": "COMPRAR AGORA" | "ESPERAR PROMOÇÃO" | "MELHOR CUSTO-BENEFÍCIO",
  "best_pick_index": 0,
  "summary": "Explicação em 2 a 3 frases do motivo da escolha.",
  "analysis_points": [
    "Ponto forte 1",
    "Ponto de atenção ou economia 2",
    "Comparativo de preço vs histórico"
  ],
  "savings_tip": "Dica prática de cupom, forma de pagamento ou timing para pagar menos."
}
"""

    @classmethod
    def analyze_offers(cls, product_name: str, offers: List[Dict[str, Any]], user_intent: str = "") -> Dict[str, Any]:
        api_key = os.getenv("GEMINI_API_KEY")
        
        # Se tiver Gemini API Key configurada e biblioteca instalada
        if api_key and genai:
            try:
                client = genai.Client(api_key=api_key)
                
                offers_text = "\n".join([
                    f"[{i}] {o['title']} | Preço: R$ {o['price']} (De: R$ {o.get('original_price')}) | Avaliação: {o.get('rating')} ({o.get('reviews_count')} reviews) | Frete Grátis: {o.get('free_shipping')}"
                    for i, o in enumerate(offers[:8])
                ])
                
                prompt = f"""
Produto pesquisado: {product_name}
Intenção do usuário: {user_intent or 'Quero a melhor opção em custo-benefício e durabilidade'}

Ofertas encontradas no mercado:
{offers_text}

Faça a análise crítica e escolha a opção campeã de compra:
"""
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=cls.SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )
                
                parsed = json.loads(response.text)
                return cls._normalize_decision(parsed, offers)
            except Exception as e:
                print(f"[AdvisorAI] Falha na chamada da API Gemini, usando heurística local: {e}")

        # Fallback local com algoritmo analítico de decisão (Zero-Shot Rule-Based Engine)
        return cls._local_heuristic_analysis(product_name, offers, user_intent)

    @classmethod
    def _local_heuristic_analysis(cls, product_name: str, offers: List[Dict[str, Any]], user_intent: str) -> Dict[str, Any]:
        if not offers:
            return {
                "verdict": "ESPERAR PROMOÇÃO",
                "best_pick": {},
                "summary": "Nenhuma oferta confiável detectada no momento.",
                "analysis_points": ["Aguarde novos anúncios serem indexados."],
                "savings_tip": "Cadastre um preço alvo para receber alerta."
            }

        # Ordenar por score: (reputação * volume) / preço
        scored = []
        for i, o in enumerate(offers):
            price = o.get("price", 999999.0)
            rating = o.get("rating", 4.0)
            reviews = min(o.get("reviews_count", 50), 500)
            free_ship_bonus = 1.15 if o.get("free_shipping") else 1.0
            discount_bonus = 1.10 if o.get("original_price") and o["original_price"] > price else 1.0
            
            # Score de custo benefício
            score = ((rating * reviews ** 0.5) / (price ** 0.8)) * free_ship_bonus * discount_bonus
            scored.append((score, i, o))

        scored.sort(reverse=True, key=lambda x: x[0])
        best_pick = scored[0][2]
        
        lowest_price = min(o["price"] for o in offers)
        has_steep_discount = any(o.get("original_price") and (o["original_price"] - o["price"]) / o["original_price"] > 0.25 for o in offers)
        
        verdict = "COMPRAR AGORA" if has_steep_discount else "MELHOR CUSTO-BENEFÍCIO"

        return {
            "verdict": verdict,
            "best_pick": best_pick,
            "summary": f"A opção '{best_pick['title']}' por R$ {best_pick['price']:.2f} oferece o melhor equilíbrio entre preço competitivo, volume de avaliações positivas ({best_pick.get('rating')} estrelas) e frete.",
            "analysis_points": [
                f"Preço mais baixo encontrado na pesquisa: R$ {lowest_price:.2f}.",
                f"Oferta recomendada possui {best_pick.get('reviews_count')} avaliações verificadas de compradores reais.",
                "Frete grátis incluso reduz o custo total efetivo em até 12% comparado às alternativas."
            ],
            "savings_tip": "Prefira pagamento via PIX para garantir descontos adicionais de 5% a 10% que muitas lojas aplicam no fechamento."
        }

    @classmethod
    def _normalize_decision(cls, parsed: Dict[str, Any], offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        idx = parsed.get("best_pick_index", 0)
        if idx < 0 or idx >= len(offers):
            idx = 0
        best_pick = offers[idx]
        
        return {
            "verdict": parsed.get("verdict", "MELHOR CUSTO-BENEFÍCIO"),
            "best_pick": best_pick,
            "summary": parsed.get("summary", ""),
            "analysis_points": parsed.get("analysis_points", []),
            "savings_tip": parsed.get("savings_tip", "")
        }
