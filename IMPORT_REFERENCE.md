# Import reference

This reference describes the V1 import contract used by **Research → Import books** and **Research → Import reviews**. The downloadable templates in the app are generated from the same field names shown here.

## Supported inputs

- Uploaded `.csv` or `.json` files up to the Streamlit page's 20 MB upload limit.
- CSV text pasted directly into the page.
- UTF-8 or UTF-8-with-BOM text. Other encodings are rejected.
- CSV with one header row and no blank header names.
- JSON as either a top-level array or an object containing a `books` or `reviews` array.

XLSX, TSV, nested CSV structures, and unknown fields are not accepted. Convert those files to the documented CSV or JSON shape first.

Blank strings are treated as missing values. Required fields must still contain non-whitespace content. Use ISO dates in `YYYY-MM-DD` form, plain numbers without currency symbols or thousands separators, and `true` or `false` for booleans.

## Import workflow

1. Create or select the destination niche in Research.
2. Download the relevant CSV or JSON template.
3. For review imports, import the referenced books first and retain their `source_identifier` values.
4. Upload the file or paste CSV, then select **Validate and preview**.
5. Review the accepted rows and every row-level issue.
6. Select **Import valid books** or **Import valid reviews** to persist the currently valid rows.

Previewing does not write book or review records. A partially valid batch can import its accepted rows while retaining rejection details for the invalid rows. The app revalidates immediately before persistence so a duplicate created after the preview cannot slip through.

## Book fields

Only `title` is always required, but supplying a stable `source_identifier` is strongly recommended and is necessary if reviews will later reference the book.

| Field | Required | Accepted value and rule |
|---|---:|---|
| `niche` | No | Optional destination check, maximum 250 characters. When present, it must match the selected niche name or seed keyword, case-insensitively. It does not create or select a niche. |
| `source` | No | Text source label; defaults to `manual`. |
| `source_identifier` | No | Stable identifier, maximum 160 characters. The `(source, source_identifier)` pair must be unique across stored books. Review imports match this value. |
| `asin` | No | Maximum 20 characters; normalized to uppercase. It is metadata, not used as an automatic fallback identifier. |
| `title` | **Yes** | Non-empty text, maximum 500 characters. |
| `subtitle` | No | Text, maximum 500 characters. |
| `author` | No | Text, maximum 250 characters. |
| `publisher` | No | Text, maximum 250 characters. |
| `publication_date` | No | ISO date such as `2025-01-15`. |
| `format` | No | Text, maximum 50 characters. |
| `price` | No | Number greater than or equal to 0. Currency is not inferred. |
| `page_count` | No | Integer greater than or equal to 1. |
| `rating` | No | Number from 0 through 5. |
| `review_count` | No | Integer greater than or equal to 0. |
| `best_seller_rank` | No | Integer greater than or equal to 1. `bsr` is an accepted alias. |
| `category` | No | Text, maximum 250 characters. |
| `product_reference` | No | Source reference text or URL. `product_url` is an accepted alias. The app does not fetch it. |
| `description` | No | Source description text. |
| `cover_image_reference` | No | Image reference text or URL. `cover_image_url` is an accepted alias. The app does not fetch or analyze it. |
| `notes` | No | User notes retained with the book record. |

Duplicate nonblank `(source, source_identifier)` pairs are rejected both within the submitted batch and against the existing database. Missing market values remain null; the importer does not infer prices, ranks, ratings, dates, formats, or counts.

### Book CSV example

```csv
source,source_identifier,title,author,publication_date,format,price,page_count,rating,review_count,best_seller_rank
manual,BOOK-001,Example Practical Guide,Sample Author,2025-01-15,Paperback,16.99,180,4.3,125,45000
```

Quote any CSV value containing a comma, line break, or double quote according to normal CSV rules.

### Book JSON example

```json
{
  "books": [
    {
      "source": "manual",
      "source_identifier": "BOOK-001",
      "title": "Example Practical Guide",
      "author": "Sample Author",
      "format": "Paperback",
      "price": 16.99,
      "rating": 4.3,
      "review_count": 125
    }
  ]
}
```

The top level may instead be the array itself. Every array element must be an object.

## Review fields

`book_identifier` and `body` are required. A review can be imported only after exactly one book in the selected niche has a matching `source_identifier`.

| Field | Required | Accepted value and rule |
|---|---:|---|
| `book_identifier` | **Yes** | Exact `source_identifier` of one book in the selected niche, maximum 160 characters. Unknown or ambiguous identifiers are rejected. |
| `source` | No | Text source label; defaults to `manual`. |
| `source_review_identifier` | No | Stable source-side review identifier, maximum 160 characters. Stored for provenance; review-text identity is the duplicate guard. |
| `rating` | No | Integer from 1 through 5. |
| `title` | No | Text, maximum 500 characters. |
| `body` | **Yes** | Non-empty original review text. The raw text is retained. |
| `review_date` | No | ISO date such as `2026-08-01`. |
| `verified_purchase` | No | Boolean, preferably `true` or `false`. Missing remains unknown. |
| `helpful_votes` | No | Integer greater than or equal to 0. |

Book matching deliberately does not use fuzzy titles, ASIN fallback, or cross-niche lookup. If two books in the selected niche share the same `source_identifier` under different sources, the identifier is ambiguous and the row is rejected.

For duplicate detection, the app applies Unicode NFKC normalization, collapses whitespace, trims the result, and compares a case-insensitive SHA-256 hash within the matched book. The original `body` is still stored unchanged. Repeated text for different books remains separate evidence.

### Review CSV example

```csv
book_identifier,source,source_review_identifier,rating,title,body,review_date,verified_purchase,helpful_votes
BOOK-001,manual,REVIEW-001,3,Useful but incomplete,The overview was clear but I wanted more worked examples.,2026-08-01,true,2
```

### Review JSON example

```json
{
  "reviews": [
    {
      "book_identifier": "BOOK-001",
      "source": "manual",
      "source_review_identifier": "REVIEW-001",
      "rating": 3,
      "title": "Useful but incomplete",
      "body": "The overview was clear but I wanted more worked examples.",
      "review_date": "2026-08-01"
    }
  ]
}
```

The top level may instead be the array itself. Every array element must be an object.

## Common rejection reasons

| Message or condition | Resolution |
|---|---|
| File must be UTF-8 encoded | Export or save the file as UTF-8 and retry. |
| CSV must include a header row | Add the exact field-name header row. |
| CSV contains an empty column name | Remove trailing delimiters or name every column. |
| Unknown or extra field | Rename it to a documented field or remove it. |
| Row must be an object | Replace a scalar/array JSON element with an object containing fields. |
| Row niche does not match the selected niche | Correct the `niche` value or select the intended destination niche. |
| Duplicate source identifier | Assign a unique stable ID or omit it only when no reviews need to reference that book. |
| No book in this niche has identifier | Import the book first or correct `book_identifier`. |
| Book identifier is ambiguous | Give the books distinct `source_identifier` values and retry. |
| Duplicate review text for this book | Remove the duplicate; capitalization and whitespace changes do not create new evidence. |
| Numeric or date validation error | Remove the value to keep it missing, or supply a value within the documented range and format. |

## Provenance and rights boundary

Each committed batch records its format, filename label, checksum, processed/imported/rejected totals, completion status, and row-level issues. Imported records link back to that data source. This provenance does not establish permission to use the source material.

Only import marketplace observations and review text you are authorized to collect, store, and analyze. The application does not bypass access controls, scrape marketplaces, or verify licensing and privacy obligations for you.
