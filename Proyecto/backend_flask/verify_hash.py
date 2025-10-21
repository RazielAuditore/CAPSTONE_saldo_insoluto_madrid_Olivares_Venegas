#!/usr/bin/env python3
import bcrypt

# Hash de tu base de datos
hash_from_db = "$2b$12$sWNliZoPbovS7U02BBhQWObhOxjlvpMalysC0rlee/6GwlbhzKVRO"

# Contraseña que quieres verificar
password = "Soulcry02"

print(f"🔍 Verificando contraseña: {password}")
print(f"🔍 Hash de la BD: {hash_from_db}")
print()

# Verificar si la contraseña coincide con el hash
try:
    if bcrypt.checkpw(password.encode('utf-8'), hash_from_db.encode('utf-8')):
        print("✅ ¡CONTRASEÑA CORRECTA!")
        print("✅ El hash corresponde a 'Soulcry02'")
    else:
        print("❌ CONTRASEÑA INCORRECTA")
        print("❌ El hash NO corresponde a 'Soulcry02'")
        
        # Generar nuevo hash para Soulcry02
        new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print()
        print("🔧 Hash correcto para 'Soulcry02':")
        print(new_hash)
        
except Exception as e:
    print(f"❌ Error verificando hash: {e}")

print()
print("=" * 50)
print("🔧 Generando hash para 'Soulcry02':")
new_hash = bcrypt.hashpw("Soulcry02".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"Nuevo hash: {new_hash}")














