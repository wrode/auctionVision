# Wildcard Agent Prompt v1

## Purpose

Identify lots with surprising, unconventional, or serendipitous appeal—pieces that don't fit standard categorization but have distinctive visual or curatorial interest. These are "curator's picks" that transcend scoring matrices.

## Input Schema

```json
{
  "lot_id": "string",
  "title": "string",
  "description": "string",
  "images": ["url"],
  "furniture_type": "string",
  "materials": ["string"],
  "condition": "string",
  "estimated_price_sek": "number or null",
  "attribution": {
    "primary_designer": "string or null",
    "confidence": "number"
  },
  "arbitrage_score": "number or null",
  "taste_score": "number or null",
  "source": "string",
  "lot_url": "string"
}
```

## Output Schema

```json
{
  "wildcard_score": "number (0.0-1.0)",
  "image_distinctiveness": "number (0.0-1.0)",
  "sculptural_presence": "number (0.0-1.0)",
  "rarity_cues": "number (0.0-1.0)",
  "material_luxury": "number (0.0-1.0)",
  "provenance_interest": "number (0.0-1.0)",
  "curator_boost": "number (0.0-0.5, applied manually)",
  "visual_story": "string (2-3 sentences about the piece's essence)",
  "why_remarkable": ["string"],
  "recommendation": "string (highlight|consider|skip)",
  "reasoning": "string"
}
```

## Component Scores

### 1. Image Distinctiveness (35% weight)

Does the piece photograph exceptionally well? Does it command visual attention?

**High (0.8-1.0)**:
- Strong silhouette, dramatic proportions
- Unusual geometry or form language
- Striking color or material contrast
- The piece *demands* to be looked at
- Multiple compelling angles in photos

**Medium (0.5-0.8)**:
- Well-composed photos, clear subject
- Some visual interest, typical for its category
- Professional presentation

**Low (0.0-0.5)**:
- Unclear images, poor lighting
- Generic form without visual drama
- Difficult to appreciate from photos alone

### 2. Sculptural Presence (20% weight)

Does the piece function as *sculpture* as much as furniture?

**High (0.8-1.0)**:
- Iconic form: Egg Chair, Swan Chair, Wishbone Chair level
- Defies "chair-ness" or "table-ness" through form
- Evokes emotional or philosophical response
- Museum-quality presence

**Medium (0.5-0.8)**:
- Elevated design with sculptural sensibility
- Goes beyond function into art
- Distinctive form language

**Low (0.0-0.5)**:
- Pure utility, functional form
- No sculptural ambition
- Conventional aesthetic

### 3. Rarity Cues (15% weight)

Is this piece rare, limited production, or hard to find?

**High (0.8-1.0)**:
- Known limited production run
- Prototype or single example
- Scarce producer or model variant
- Early/late edition with significance

**Medium (0.5-0.8)**:
- Moderate availability
- Fewer sightings in market
- Lesser-known make

**Low (0.0-0.5)**:
- Common model, widely produced
- Seen frequently in auctions
- No rarity indicators

### 4. Material Luxury (10% weight)

Does the piece showcase premium materials in an exceptional way?

**High (0.8-1.0)**:
- Rosewood or teak with visible grain
- Leather hand-dyed or naturally patinated
- Brass or chrome reflecting craftsmanship
- Material *is* the statement

**Medium (0.5-0.8)**:
- Quality materials, typical application
- Leather or hardwood, competent finish
- Interesting material pairing

**Low (0.0-0.5)**:
- Common materials
- Painted-over or disguised materials
- Cheap alternatives

### 5. Provenance Interest (10% weight)

Is there a compelling story or documented history?

**High (0.8-1.0)**:
- Designer-signed or documented
- Museum provenance or exhibition history
- Maker's mark or serial number visible
- Published references or catalog entry
- Family heirloom with credible backstory

**Medium (0.5-0.8)**:
- Plausible attribution with good evidence
- Regional provenance (e.g., "Swedish estate")
- Maker/producer likely identifiable

**Low (0.0-0.5)**:
- Unknown origin
- "Attributed to" without evidence
- No provenance documentation

## Composite Score Calculation

```
wildcard_score = (
  0.35 × image_distinctiveness +
  0.20 × sculptural_presence +
  0.15 × rarity_cues +
  0.10 × material_luxury +
  0.10 × provenance_interest +
  0.10 × curator_boost  [optional manual boost by human curator]
)
```

**Note**: Curator boost (0.0-0.5) is applied manually for pieces that defy quantification—pieces the curator just *knows* are special.

## Recommendation Logic

```python
if wildcard_score >= 0.75:
    recommendation = "highlight"
elif wildcard_score >= 0.5:
    recommendation = "consider"
else:
    recommendation = "skip"
```

**Exception**: Even with lower wildcard_score, if provenance_interest OR visual_story is compelling, consider upgrade to "consider".

## Qualitative Assessment

### Visual Story (2-3 sentences)

Capture the essence of why this piece matters:
- What makes it visually unforgettable?
- What does the form communicate?
- What does the material/finish tell us?
- How does it fit into design history?

**Examples**:
- "A teak sideboard whose sculptural proportions transcend storage function—the grain patterns and joinery detail suggest masterful hand finishing."
- "This molded fiberglass lounge chair defies expectation with organic curves; its condition reveals decades of use that paradoxically enhance its appeal."
- "A brass-mounted credenza that marries Minimalism with craft sensibility; the material choices suggest a maker unafraid of luxury."

### Why Remarkable (bullet points)

List 3-5 reasons this piece stands out:
- Unique form in category
- Exceptional material handling
- Proven rarity or scarcity
- Museum-quality presence
- Unexplored or undervalued designer
- Exceptional condition despite age
- Compelling documented history

## Interaction with Other Agents

- **Low Arbitrage Score + High Wildcard Score**: The piece may be overpriced relative to market fundamentals, but has significant curatorial/aesthetic value. Flag as "interesting despite cost."
- **Low Taste Score + High Wildcard Score**: Appeals to different sensibility—contemporary design, craft-focused, experimental. Worth surfacing separately.
- **All Scores Low + High Wildcard Score**: A hidden gem, possibly mis-catalogued or underestimated. Investigate further.

## Failure Convention

If images unavailable or piece is purely utilitarian:

```json
{
  "wildcard_score": 0.0,
  "recommendation": "skip",
  "reasoning": "Insufficient visual data or no distinctive characteristics to evaluate"
}
```

## Example Scenarios

### Scenario 1: Iconic Sculptural Piece

**Input**:
- Title: "Arne Jacobsen Swan Chair, Fritz Hansen, 1960"
- Images: Exceptional photography, silhouette clear
- Material: Original upholstery, patina visible
- Provenance: "From architect's personal collection"

**Evaluation**:
- Image distinctiveness: 0.95 (iconic silhouette, exceptional photos)
- Sculptural presence: 1.0 (Swan Chair is sculpture masquerading as furniture)
- Rarity cues: 0.75 (not rare, but early production likely)
- Material luxury: 0.85 (original upholstery is premium)
- Provenance interest: 0.90 (architect's collection adds credibility)
- Curator boost: 0.2 (iconic enough without extra boost)

**Score**: (0.35 × 0.95) + (0.20 × 1.0) + (0.15 × 0.75) + (0.10 × 0.85) + (0.10 × 0.90) + (0.10 × 0.2)
= 0.3325 + 0.20 + 0.1125 + 0.085 + 0.09 + 0.02 = **0.8825**

**Output**:
```json
{
  "wildcard_score": 0.88,
  "recommendation": "highlight",
  "visual_story": "The Swan Chair epitomizes Jacobsen's biomorphic modernism—its seamless form suggests organic growth rather than industrial design. The original upholstery bears patina that testifies to decades of use by an architect of vision.",
  "why_remarkable": [
    "Jacobsen's most iconic furniture design",
    "Original Fritz Hansen production",
    "Exceptional photographic presentation",
    "Documented provenance (architect's collection)",
    "Patina suggests authenticity and lived history"
  ]
}
```

### Scenario 2: Hidden Gem (Lesser-Known Designer)

**Input**:
- Title: "Rosewood Credenza, Unknown Maker, c.1965"
- Images: Good detail shots, material visible
- Material: Rosewood with visible grain, brass handles
- No attribution, no provenance

**Evaluation**:
- Image distinctiveness: 0.7 (good detail, material clear)
- Sculptural presence: 0.65 (refined proportions, subtle design)
- Rarity cues: 0.8 (unknown maker, possibly scarce)
- Material luxury: 0.9 (rosewood grain is spectacular)
- Provenance interest: 0.4 (no documentation, unknown maker)
- Curator boost: 0.3 (material alone warrants investigation)

**Score**: (0.35 × 0.7) + (0.20 × 0.65) + (0.15 × 0.8) + (0.10 × 0.9) + (0.10 × 0.4) + (0.10 × 0.3)
= 0.245 + 0.13 + 0.12 + 0.09 + 0.04 + 0.03 = **0.655**

**Output**:
```json
{
  "wildcard_score": 0.655,
  "recommendation": "consider",
  "visual_story": "This rosewood credenza is a lesson in material honesty—the grain patterns are unadorned, allowed to speak for themselves. The proportions suggest a maker of restraint and skill, possibly underrepresented in design historiography.",
  "why_remarkable": [
    "Exceptional rosewood grain display",
    "Unknown maker suggests research opportunity",
    "Refined proportions without ornamentation",
    "Rarity cues in form and production quality",
    "Potential for attribution detective work"
  ]
}
```

## Related Configuration

- Scoring thresholds: `config/scoring.yaml` (wildcard.thresholds)
- Weights: `config/scoring.yaml` (wildcard.weights)
