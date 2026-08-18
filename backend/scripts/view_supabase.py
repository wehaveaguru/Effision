"""Quick script to view what's stored in the Supabase documents table."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from app.db.supabase_client import get_client

client = get_client()
resp = client.table("documents").select("id, content, metadata").execute()
rows = resp.data

print(f"\nTotal rows in Supabase documents table: {len(rows)}\n")
for row in rows:
    meta = row.get("metadata", {})
    title = meta.get("title", "(no title)") if isinstance(meta, dict) else ""
    brand = meta.get("brand", "") if isinstance(meta, dict) else ""
    content_preview = row.get("content", "")[:80].replace("\n", " ")
    print(f"  [id={row['id']}] {title} | Brand: {brand}")
    print(f"           {content_preview}...")
    print()
