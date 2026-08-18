import os
import time
import json
from dotenv import load_dotenv
from groq import Groq
# pyrefly: ignore [missing-import]
from llama_cloud import LlamaCloud
from pydantic import BaseModel, Field

class Product(BaseModel):
    product_name: str = Field(description="The product name")
    brand_name: str = Field(description="What brand the product is related to")
    product_price: float = Field(description="Amount of money received in procurement")
    product_image: str = Field(description="Link to product image")
    product_star_rating: float = Field(description="Ratings of a product")
    number_of_ratings: int = Field(description="Number of ratings")

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
client = LlamaCloud(api_key=os.getenv("LLAMA_CLOUD_API_KEY"))

with open("./amazon_product.csv", "rb") as f:
    file = client.files.create(file=f, purpose="extract")

job = client.extract.create(
    file_input=file.id,
    configuration={
        "data_schema": Product.model_json_schema(),
        "extraction_target": "per_table_row",
        "tier": "agentic"
    }
)

while job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
    time.sleep(2)
    job = client.extract.get(job.id)

if job.status != "COMPLETED":
    raise RuntimeError(f"Extraction failed with status: {job.status}")

data = job.extract_result


batch_size = 5
llm_batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

enriched_catalog = []

SYSTEM_PROMPT = """You are an expert e-commerce copywriter and Product Information Management (PIM) specialist. 
Your task is to transform the provided array of raw products into rich, engaging, and comprehensive product profiles.

Output strictly valid JSON with the top-level key "products" containing an array of enriched objects:
{
  "products": [
    {
      "title": "Optimized, SEO-friendly product title (Brand + Product Line + Key Specs)",
      "brand": "Brand name",
      "category_hierarchy": ["Category", "Subcategory", "Product Type"],
      "summary": "A punchy 1-2 sentence hook highlighting the core value proposition.",
      "enriched_description": "A comprehensive, persuasive description detailing use cases and benefits.",
      "key_features": [
        "Feature benefit statement 1",
        "Feature benefit statement 2",
        "Feature benefit statement 3"
      ],
      "technical_specifications": {
        "key": "value"
      },
      "attributes": {
        "color": "...",
        "material": "...",
        "dimensions": "...",
        "target_audience": "..."
      },
      "search_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  ]
}

Guidelines:
- Process every product present in the input list.
- Return ONLY the JSON object. No markdown fences or preamble."""

for idx, batch in enumerate(llm_batches):
    print(f"Enriching batch {idx + 1} of {len(llm_batches)}...")
    
    cleaned_data = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Enrich these products:\n{json.dumps(batch)}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    

    result = json.loads(cleaned_data.choices[0].message.content)
    batch_products = result.get("products", [])
    
    if isinstance(batch_products, list):
        enriched_catalog.extend(batch_products)
    else:
        enriched_catalog.append(batch_products)

print(enriched_catalog[0])