# src/api/reports/monthly_dre.py
import os
import sys
import calendar
from datetime import date
from decimal import Decimal

# Framework FastAPI
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# --- VERCEL PATH FIX (STILL REQUIRED) ---
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )
)
# --- FIM DA MODIFICAÇÃO ---

from lib.prisma_client import Prisma

# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
app = FastAPI(
    title="DRE & Reports API",
    description="Gera o DRE mensal e faz a reconciliação.",
    docs_url="/docs" 
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
#  Endpoint da API de Relatório
# ==============================================================================
@app.get("/")
async def get_monthly_dre(year: int = Query(...), month: int = Query(...)):
    """
    Gera o DRE mensal com base nos dados internos (competência)
    e faz a reconciliação com os dados bancários (caixa).
    """

    db = Prisma()
    await db.connect()

    try:
        # Calcular datas de início e fim para o mês
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

        # --- 1. DRE INTERNO (Baseado no sistema) ---
        # Busca todos os recebimentos pagos com vencimento no mês
        paid_receivables = await db.internalreceivables.find_many(
            where={
                'status': 'Paga',
                'due_date': {'gte': start_date, 'lte': end_date}
            }
        )
        # Busca todos os pagamentos pagos com vencimento no mês
        paid_payments = await db.internalpayments.find_many(
            where={
                'status': 'Paga',
                'due_date': {'gte': start_date, 'lte': end_date}
            }
        )

        # Soma os totais
        total_receitas = sum(r.paid_amount for r in paid_receivables if r.paid_amount) or Decimal(0)
        total_despesas = sum(p.paid_amount for p in paid_payments if p.paid_amount) or Decimal(0)

        # --- 2. RECONCILIAÇÃO BANCÁRIA (Baseado no banco) ---
        # Busca todos os créditos bancários no mês
        bank_credits = await db.banktransactions.find_many(
            where={
                'type': 'credit',
                'transaction_date': {'gte': start_date, 'lte': end_date}
            }
        )
        # Busca todos os débitos bancários no mês
        bank_debits = await db.banktransactions.find_many(
            where={
                'type': 'debit',
                'transaction_date': {'gte': start_date, 'lte': end_date}
            }
        )

        total_received_bank = sum(t.amount_decimal for t in bank_credits) or Decimal(0)
        total_paid_bank = sum(t.amount_decimal for t in bank_debits) or Decimal(0)

        # --- 3. Serializa e Retorna ---
        # model_dump(to_json=True) converte Decimal para float e datetime para str
        return JSONResponse({
            "dre": {
                "total_receitas": float(total_receitas),
                "total_despesas": float(total_despesas),
                "net_profit": float(total_receitas - total_despesas),
            },
            "reconciliation": {
                "total_received_bank": float(total_received_bank),
                "total_paid_bank": float(total_paid_bank),
                "discrepancy_receitas": float(total_received_bank - total_receitas),
                "discrepancy_despesas": float(total_paid_bank - total_despesas),
            },
            "lists": {
                "receitas": [r.model_dump(to_json=True) for r in paid_receivables],
                "despesas": [p.model_dump(to_json=True) for p in paid_payments],
            }
        })

    except Exception as e:
        print(f"--- ERRO CRÍTICO (DRE): {str(e)} ---")
        raise HTTPException(status_code=500, detail=f"Falha ao gerar relatório: {e}")
    finally:
        if db.is_connected():
            await db.disconnect()