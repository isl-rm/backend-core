from app.core.security import get_password_hash, verify_password

try:
    p = "password123"
    h = get_password_hash(p)
    print(f"Hash success: {h}")
    v = verify_password(p, h)
    print(f"Verify success: {v}")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
