# src/lib/parsers/internal_parser.py
import pdfplumber
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional

# ==============================================================================
#  HELPER FUNCTIONS
# ==============================================================================

def _clean_text(text: Optional[str]) -> str:
    """Limpa o texto de uma célula do PDF, lidando com None."""
    if text:
        return text.replace('\n', ' ').strip()
    return ""

def _to_date_obj(date_str: Optional[str]) -> Optional[datetime]:
    """Converte 'dd/mm/YYYY' para um objeto datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except (ValueError, TypeError):
        return None

def _to_decimal(val_str: Optional[str]) -> Optional[Decimal]:
    """Converte '1.234,56' para Decimal, lidando com None e '0,00'."""
    if not val_str:
        return None
    try:
        cleaned = val_str.strip().replace('.', '').replace(',', '.')
        if not cleaned:
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None

# ==============================================================================
#  PARSER: PAGAMENTOS (novembro-pagamentos.pdf)
# ==============================================================================
def parse_pagamentos(pdf_path: str, source_file_name: str) -> List[Dict[str, Any]]:
    """
    Parseia o PDF de "Contas a Pagar".
   
    """
    all_transactions = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    for row in table:
                        # Pula a linha de cabeçalho
                        if not row or _clean_text(row[0]) == "Categoria":
                            continue
                        
                        # Uma linha válida tem 11 colunas
                        if len(row) == 11:
                            try:
                                # Coluna 3: "Parcela Emissão"
                                col3_parts = _clean_text(row[3]).split()
                                parcela = col3_parts[-1] if col3_parts else None
                                emissao = col3_parts[0] if col3_parts else None
                                
                                # Coluna 4: "Vencimento Valor Integral"
                                col4_parts = _clean_text(row[4]).split()
                                valor_integral = col4_parts[-1] if col4_parts else None
                                vencimento = col4_parts[0] if col4_parts else None

                                data = {
                                    "category": _clean_text(row[0]),
                                    "entity_name": _clean_text(row[1]),
                                    "entity_type": _clean_text(row[2]),
                                    "installment": parcela,
                                    "issue_date": _to_date_obj(emissao),
                                    "due_date": _to_date_obj(vencimento),
                                    "full_amount": _to_decimal(valor_integral),
                                    "discount_amount": _to_decimal(row[5]),
                                    "updated_amount": _to_decimal(row[6]),
                                    "paid_amount": _to_decimal(row[7]),
                                    "notes": _clean_text(row[8]),
                                    "status": _clean_text(row[9]),
                                    "source_file_name": source_file_name
                                }
                                all_transactions.append(data)
                            except Exception as e:
                                print(f"Erro ao processar linha (pagamentos): {row} | Erro: {e}")
                                continue
        
        return all_transactions

    except Exception as e:
        print(f"Erro no parse_pagamentos: {e}")
        return []


# ==============================================================================
#  PARSER: RECEBIMENTOS (novembro-recebimentos.pdf)
# ==============================================================================

def _process_recebimento_row(row: List[Optional[str]], source_file_name: str) -> Optional[Dict[str, Any]]:
    """Função helper para processar uma linha (ou buffer) de recebimento."""
    try:
        if len(row) < 16:
            return None

        data = {
            "category": _clean_text(row[0]),
            "entity_name": _clean_text(row[1]),
            "entity_type": _clean_text(row[2]),
            "phone": _clean_text(row[3]),
            "financial_responsible": _clean_text(row[4]),
            "installment": _clean_text(row[5]),
            "issue_date": _to_date_obj(_clean_text(row[6])),
            "due_date": _to_date_obj(_clean_text(row[7])),
            "full_amount": _to_decimal(_clean_text(row[8])),
            "discount_amount": _to_decimal(_clean_text(row[9])),
            "updated_amount": _to_decimal(_clean_text(row[10])),
            "paid_amount": _to_decimal(_clean_text(row[11])),
            "notes": _clean_text(row[12]),
            "status": _clean_text(row[13]),
            "contract_status": _clean_text(row[14]),
            "source_file_name": source_file_name
        }
        
        # Validação mínima: deve ter um nome e uma data de vencimento
        if not data["entity_name"] or not data["due_date"]:
            return None
            
        return data
    except Exception as e:
        print(f"Erro ao processar buffer (recebimentos): {row} | Erro: {e}")
        return None

def parse_recebimentos(pdf_path: str, source_file_name: str) -> List[Dict[str, Any]]:
    """
    Parseia o PDF de "Contas a Receber".
    Este parser lida com linhas que se quebram em várias linhas de tabela.
   
    """
    all_transactions = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    row_buffer: List[Optional[str]] = []
                    
                    for row in table:
                        if not row:
                            continue
                        
                        # Pula a linha de cabeçalho
                        if _clean_text(row[0]) == "Categoria":
                            continue
                        
                        # Se a primeira célula NÃO está vazia, é uma nova transação.
                        # Processamos o buffer anterior e iniciamos um novo.
                        if _clean_text(row[0]):
                            if row_buffer:
                                processed = _process_recebimento_row(row_buffer, source_file_name)
                                if processed:
                                    all_transactions.append(processed)
                            row_buffer = list(row)
                        
                        # Se a primeira célula ESTÁ vazia, é uma continuação.
                        # Anexamos os dados ao buffer existente.
                        elif row_buffer:
                            # Colunas que podem ter múltiplas linhas:
                            # 1: Entidade-Nome, 3: Telefone, 4: Responsável
                            if len(row) > 4:
                                row_buffer[1] = _clean_text(row_buffer[1]) + " " + _clean_text(row[1])
                                row_buffer[3] = _clean_text(row_buffer[3]) + " " + _clean_text(row[3])
                                row_buffer[4] = _clean_text(row_buffer[4]) + " " + _clean_text(row[4])
                    
                    # Processa a última transação no buffer
                    if row_buffer:
                        processed = _process_recebimento_row(row_buffer, source_file_name)
                        if processed:
                            all_transactions.append(processed)
        
        return all_transactions

    except Exception as e:
        print(f"Erro no parse_recebimentos: {e}")
        return []