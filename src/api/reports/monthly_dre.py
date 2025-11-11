import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
# --- FIX: Import datetime and time ---
from datetime import date, datetime, time
import json

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
# --- FIX: IMPORT PRISMA TYPES ---
from lib.prisma_client.types import (
    BankTransactionsWhereInput, 
    InternalReceivablesWhereInput, 
    DateTimeFilter
)

# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
# --- FIX: Define the 'app' variable ---
app = FastAPI(
    title="Monthly DRE Report API",
    description="Lida com a geração de relatórios DRE.",
    docs_url="/docs" 
)

# ==============================================================================
#  Helper Functions (com tipagem correta)
# ==============================================================================
# --- FIX: Update function signature to accept datetime ---
async def get_bank_transactions(db: Prisma, start_date: datetime, end_date: datetime):
    """Busca transações bancárias dentro de um período."""
    
    # --- FIX: Use o DateTimeFilter tipado ---
    date_filter = DateTimeFilter(gte=start_date, lte=end_date)
    
    # --- FIX: Use o BankTransactionsWhereInput tipado ---
    where_clause = BankTransactionsWhereInput(
        transaction_date=date_filter
    )
    
    # Agora Pylance está feliz
    return await db.banktransactions.find_many(where=where_clause)

# --- FIX: Update function signature to accept datetime ---
async def get_internal_receivables(db: Prisma, start_date: datetime, end_date: datetime):
    """Busca recebíveis internos dentro de um período."""
    
    # --- FIX: Use o DateTimeFilter tipado ---
    date_filter = DateTimeFilter(gte=start_date, lte=end_date)
    
    # --- FIX: Use o InternalReceivablesWhereInput tipado ---
    # O campo 'data_recebimento' estava incorreto.
    # Com base na sua assinatura, o campo correto é 'due_date' (data de vencimento)
    # ou 'issue_date' (data de emissão). Ajuste se necessário.
    where_clause = InternalReceivablesWhereInput(
        due_date=date_filter 
    )
    
    return await db.internalreceivables.find_many(where=where_clause)

# ==============================================================================
#  Endpoint da API
# ==============================================================================
@app.get("/")
async def handle_get_monthly_dre(
    start_date_str: str = Query(..., alias="startDate"),
    end_date_str: str = Query(..., alias="endDate")
):
    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD.")

    db = Prisma()
    try:
        await db.connect()
        
        # --- FIX: Convert date objects to datetime objects for the query ---
        # start_date becomes 00:00:00 on that day
        # end_date becomes 23:59:59 on that day
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        bank_tx_models = await get_bank_transactions(db, start_datetime, end_datetime)
        internal_rx_models = await get_internal_receivables(db, start_datetime, end_datetime)
        
        # ... Lógica de processamento do DRE ...
        # (Exemplo: agrupar dados, etc.)
        
        # --- FIX: Correção do 'to_json' ---
        # Não chame `.to_json()`. Use `.model_dump()` para converter
        # os modelos Pydantic em dicts. O FastAPI/JSONResponse
        # irá serializar os dicts para JSON automaticamente.
        
        bank_tx_data = [tx.model_dump() for tx in bank_tx_models]
        internal_rx_data = [rx.model_dump() for rx in internal_rx_models]

        return JSONResponse(
            status_code=200,
            content={
                "report_period": {
                    "start": start_date_str,
                    "end": end_date_str
                },
                "summary": {
                    "total_bank_transactions": len(bank_tx_data),
                    "total_internal_receivables": len(internal_rx_data)
                },
                "data": {
                    "bank_transactions": bank_tx_data,
                    "internal_receivables": internal_rx_data
                }
            }
        )
        
    except Exception as e:
        # Tente logar o erro de forma mais clara
        print(f"Erro ao gerar DRE: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {str(e)}")
    finally:
        if db.is_connected():
            await db.disconnect()