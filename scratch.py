# coding: utf-8
import re

def extraer_campo(campo, texto_completo):
    # No necesitamos es_ultimo. [^"\\]* siempre se detiene en la comilla de cierre
    # o al final de la cadena si se truncó!
    patron = f'"{campo}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)'
    match = re.search(patron, texto_completo)
    if match:
        val = match.group(1)
        if val.endswith('\\'):
            val = val[:-1]
        val = val.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
        return val
    return None

texto1 = '''{
  "resultado_final": "## Decisiones Tomadas\\nSe discutió el \\"plan\\".",
  "resumen": "La reunión se centró en la ge
'''
texto2 = '''{
  "resumen": "La reunión se centró en la ge",
  "resultado_final": "## Decisiones Tomadas\\nSe discutió el
'''
texto3 = '''{
  "resumen": "La reunión se centró en la gestión"
'''
texto4 = '''{
  "resultado_final": "## Decisiones\\nOk",
  "resumen": "La reunión"
}'''

for i, t in enumerate([texto1, texto2, texto3, texto4]):
    print(f"\\n--- TEXTO {i+1} ---")
    print("rf:", extraer_campo("resultado_final", t))
    print("res:", extraer_campo("resumen", t))
