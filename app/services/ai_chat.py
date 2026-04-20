import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

def ask_ollama(prompt: str, context: str = "") -> str:
    full_prompt = f"""Kamu adalah asisten AI untuk analisis data perbankan dan sales.
Jawab dalam Bahasa Indonesia, singkat dan profesional.

{f'Konteks data: {context}' if context else ''}

Pertanyaan: {prompt}
"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": full_prompt,
            "stream": False
        }, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("response", "Tidak ada respons dari AI.")
        return f"Error dari Ollama: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return "⚠️ Ollama tidak berjalan. Pastikan `ollama serve` sudah dijalankan dan model llama3 sudah di-pull."
    except Exception as e:
        return f"Error: {str(e)}"


def chat_with_fraud_context(prompt: str, fraud_result: dict) -> str:
    context = json.dumps({
        "customer": fraud_result.get("customer_name"),
        "final_status": fraud_result.get("agent3", {}).get("final_status"),
        "combined_score": fraud_result.get("agent3", {}).get("combined_score"),
        "agent1_status": fraud_result.get("agent1", {}).get("status"),
        "agent2_details": fraud_result.get("agent2", {}).get("details"),
    }, ensure_ascii=False, indent=2)
    return ask_ollama(prompt, context)


def chat_with_sales_context(prompt: str, sales_data: dict) -> str:
    context = json.dumps({
        "total_revenue": sales_data.get("total_revenue"),
        "total_transactions": sales_data.get("total_transactions"),
        "top_category": sales_data.get("by_category", [{}])[0],
        "top_region": sales_data.get("by_region", [{}])[0],
        "top_product": sales_data.get("top_products", [{}])[0],
    }, ensure_ascii=False, indent=2)
    return ask_ollama(prompt, context)