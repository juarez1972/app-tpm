#Ferramenta de Pentest automatizado integrado com Gemini

#Preparação do Ambiente
python -m venv venv/
source venv/bin/activate
pip install google-genai python-dotenv

#Estrutura do diretório
config.env                                     
passwords.txt                                  
pentest.py                                      
users.txt
teste_gemini.py

#Execução de teste conexão com Gemini
python teste_gemini.py

#Execução do Pentest
python pentest
