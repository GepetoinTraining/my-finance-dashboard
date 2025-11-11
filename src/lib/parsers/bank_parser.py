import pdfplumber
import re
from typing import List, Dict, Any, Optional

# ==============================================================================
#  HELPER FUNCTIONS (Corrigidos para aceitar None)
# ==============================================================================

def _clean_text(text: Optional[str]) -> str:
    """Limpa o texto de uma célula do PDF, lidando com None."""
    if text:
        return text.replace('\n', ' ').strip()
    return ""

def _is_date_like(s: Optional[str]) -> bool:
    """Verifica se uma string parece 'dd/mm/yyyy', lidando com None."""
    s_clean = _clean_text(s) # s_clean será sempre str
    if s_clean:
        return bool(re.match(r'^\d{2}/\d{2}/\d{4}$', s_clean))
    return False

def _is_value_like(s: Optional[str]) -> bool:
    """Verifica se uma string parece '1.234,56 (+)', lidando com None."""
    s_clean = _clean_text(s) # s_clean será sempre str
    if s_clean:
        return bool(re.search(r'(\(\+\)|\(-\))$', s_clean))
    return False

# ==============================================================================
#  PARSER PÚBLICO: 2024
# ==============================================================================
def parse_2024(pdf_path: str, source_file_name: str) -> List[Dict[str, Any]]:
    """
    [LIB V6] Parseia PDFs no formato 2024.
    Projetado para ser importado como um módulo.
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
                        # A checagem _is_date_like(row[0]) agora é segura
                        if len(row) == 8 and _is_date_like(row[0]):
                            
                            balance_date = _clean_text(row[0])
                            movement_date = _clean_text(row[1])
                            raw_value = _clean_text(row[6])
                            raw_balance = _clean_text(row[7])

                            type = 'credit' if ' C' in raw_value else 'debit'
                            amount_str = raw_value.replace(' C', '').replace(' D', '').replace('.', '').replace(',', '.')
                            
                            try:
                                amount = float(amount_str)
                            except ValueError:
                                amount = 0.0

                            transaction_data = {
                                "transaction_date": movement_date or balance_date,
                                "posting_date": balance_date,
                                "type": type,
                                "amount": amount,
                                "raw_history_text": _clean_text(row[4]),
                                "raw_value_text": raw_value,
                                "raw_balance_text": raw_balance,
                                "source_file_name": source_file_name,
                                "raw_json_data": {
                                    "lote": _clean_text(row[3]),
                                    "document": _clean_text(row[5]),
                                    "agency_origin": _clean_text(row[2])
                                }
                            }
                            all_transactions.append(transaction_data)
        
        return all_transactions

    except Exception as e:
        print(f"Erro no parse_2024: {e}")
        return []

# ==============================================================================
#  PARSER PÚBLICO: 2025
# ==============================================================================

_line_regex_2025 = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+'        # 1: Date
    r'(\d*)\s+'                      # 2: Lote
    r'([\d\.]*)\s+'                  # 3: Document
    r'(.*?)\s+'                      # 4: History (non-greedy)
    r'([\d\.,]+\s\([\+\-]\))$',       # 5: Value
    re.DOTALL | re.MULTILINE
)

def parse_2025(pdf_path: str, source_file_name: str) -> List[Dict[str, Any]]:
    """
    [LIB V6] Parseia PDFs no formato 2025.
    Usa Regex no texto puro, abandonando extract_tables().
    """
    all_transactions = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                
                header_text = page.search("Lançamentos")
                footer_text_1 = page.search("Informações Adicionais")
                footer_text_2 = page.search("Lançamentos Futuros")

                crop_top = header_text[0]['bottom'] if header_text else 50
                crop_bottom_1 = footer_text_1[0]['top'] if footer_text_1 else page.height
                crop_bottom_2 = footer_text_2[0]['top'] if footer_text_2 else page.height
                crop_bottom = min(crop_bottom_1, crop_bottom_2, page.height) - 5
                
                if crop_top >= crop_bottom:
                    continue
                    
                bbox = (0, crop_top, page.width, crop_bottom)
                cropped_page = page.crop(bbox)
                page_text = cropped_page.extract_text()

                if not page_text:
                    continue
                    
                matches = _line_regex_2025.finditer(page_text)
                
                for match in matches:
                    date = match.group(1).strip()
                    raw_value = match.group(5).strip()
                    
                    type = 'credit' if '(+)' in raw_value else 'debit'
                    amount_str = raw_value.replace(' (+)', '').replace(' (-)', '').replace('.', '').replace(',', '.')
                    
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        amount = 0.0

                    transaction_data = {
                        "transaction_date": date,
                        "posting_date": date,
                        "type": type,
                        "amount": amount,
                        "raw_history_text": match.group(4).strip().replace('\n', ' '),
                        "raw_value_text": raw_value,
                        "raw_balance_text": None,
                        "source_file_name": source_file_name,
                        "raw_json_data": {
                            "lote": match.group(2).strip(),
                            "document": match.group(3).strip()
                        }
                    }
                    all_transactions.append(transaction_data)

        return all_transactions

    except Exception as e:
        print(f"Erro no parse_2025: {e}")
        return []