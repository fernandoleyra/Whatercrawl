---
description: Scrape a URL and extract structured data fields defined by the user. Use when asked to extract specific fields, get structured data, or parse specific information from a page.
triggers:
  - "extract"
  - "get structured data"
  - "parse fields from"
  - "extract the price"
  - "extract product info"
---

# watercrawl-extract

Scrape a URL and extract structured JSON fields defined by the user.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required.
   - `schema` — the fields to extract. Can be:
     - Inline JSON: `{ "title": "string", "price": "number" }`
     - Natural language: `"title, price as a number, whether it's in stock"`
     - Not provided: ask the user what fields they want

2. **If schema not provided**, ask:
   > "What fields would you like to extract? For example: `{ \"title\": \"string\", \"price\": \"number\", \"in_stock\": \"boolean\" }`"

3. **Fetch the page** using WebFetch.

4. **Extract fields** using your intelligence:
   - For each field in the schema, find the corresponding value in the content
   - Type coercion: convert "$29.99" to `29.99` for `number` type
   - For booleans: "In Stock" → `true`, "Out of Stock" → `false`
   - If a field cannot be found, set it to `null`

5. **Return**:
   ```json
   {
     "url": "...",
     "data": {
       "field1": "value1",
       "field2": 42
     },
     "warnings": ["field3 not found in page content"]
   }
   ```

6. Append: "Extraction performed by reading the page content. For high-stakes use cases, verify values manually."
