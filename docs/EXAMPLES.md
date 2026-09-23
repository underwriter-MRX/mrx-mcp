# Three source-linked workflows

## Inherited mineral rights

1. Call `mrx_search_guides` with `{"query":"inherited mineral rights","limit":5}`.
2. Select a guide matching the user's general question and jurisdiction.
3. Call `mrx_read_page` with its exact returned `canonical_url`.
4. Summarize the source with a clickable citation and retrieval date. Separate records that may help from proof of current ownership.

## Understanding an offer document

Search for `offer letter intent purchase agreement`. Read the matching guide before explaining document categories. State what the source actually supports and what requires a qualified human review. Do not decide whether someone should sign or sell.

## A relevant next step

Call `mrx_get_started`. Explain the current public MRX journey and offer its website link if relevant. The user chooses whether to visit and submit a request. The tool does not make a booking, transfer documents or claim a review has happened.

## Troubleshooting an answer

If no relevant guide appears, say so. Search is based on URL words, so try a shorter general topic once. Do not fabricate a source. If integrity verification fails, stop using that page until it passes; report the error without including personal information.
