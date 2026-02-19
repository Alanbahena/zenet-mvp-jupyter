# Architecture diagram sources

Mermaid source files (`.mmd`) are the single source of truth. The `.md` architecture docs embed the same Mermaid blocks and reference the exported `.png` images.

**Regenerate PNGs** (from this directory):

```bash
# One file (use long-form flags with npx)
npx -p @mermaid-js/mermaid-cli mmdc --input taxonomy-02-hierarchy-example.mmd --output taxonomy-02-hierarchy-example.png

# All .mmd files (bash)
for f in *.mmd; do npx -p @mermaid-js/mermaid-cli mmdc --input "$f" --output "${f%.mmd}.png"; done
```

Requires Node.js. After adding or editing a `.mmd`, regenerate the corresponding `.png` so image links in the architecture docs work. The `.md` files also embed the Mermaid blocks, so many viewers (e.g. GitHub) will render the diagram even if the PNG is missing.
