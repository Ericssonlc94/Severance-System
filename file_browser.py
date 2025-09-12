import tkinter as tk
from tkinter import filedialog
import sys
import json

def main(filetypes_arg=None):
    """Abre uma janela de diálogo de arquivo e imprime o caminho selecionado."""
    root = tk.Tk()
    root.withdraw()  # Oculta a janela principal do tkinter
    
    # Define os tipos de arquivo padrão se nenhum for fornecido
    if filetypes_arg is None:
        filetypes_arg = [("Todos os arquivos", "*.*")] # Default to all files if not specified

    # Abre o diálogo para selecionar o arquivo
    filepath = filedialog.askopenfilename(
        title="Selecione o arquivo", # Generic title
        filetypes=filetypes_arg
    )
    
    # Imprime o caminho para que o script principal possa capturá-lo
    if filepath:
        print(filepath)

if __name__ == "__main__":
    # Se argumentos forem passados, assume que o primeiro é uma string JSON de filetypes
    if len(sys.argv) > 1:
        try:
            filetypes_from_arg = json.loads(sys.argv[1])
            main(filetypes_from_arg)
        except json.JSONDecodeError:
            # Fallback to default if JSON is invalid
            main()
    else:
        main()