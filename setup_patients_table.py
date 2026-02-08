import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

print("Verificando estrutura da tabela patients...")

# Verificar se a coluna status existe
try:
    # Tentar inserir um registro de teste
    test_res = supabase.table("patients").select("status").limit(1).execute()
    print("✅ Coluna 'status' já existe na tabela patients")
except Exception as e:
    if "status" in str(e).lower():
        print("❌ Coluna 'status' não existe. Criando...")
        print("\nExecute este SQL no Supabase Dashboard:")
        print("""
ALTER TABLE patients ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE patients ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """)
    else:
        print(f"Erro: {e}")

# Listar pacientes existentes
print("\n📋 Pacientes cadastrados:")
try:
    res = supabase.table("patients").select("*").execute()
    if res.data:
        for p in res.data:
            status = p.get('status', 'N/A')
            print(f"  - {p['name']} (ID: {p['telegram_id']}) - Status: {status}")
    else:
        print("  Nenhum paciente cadastrado")
except Exception as e:
    print(f"Erro ao listar pacientes: {e}")
