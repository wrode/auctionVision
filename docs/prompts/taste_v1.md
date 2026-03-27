# Taste Agent Prompt v1

## Purpose

Score a lot based on aesthetic and stylistic merit for a curator interested in Scandinavian Modern design. Does this piece align with the taste profile of a discerning collector?

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
  "era_estimate": "string",
  "attribution": {
    "primary_designer": "string or null",
    "confidence": "number"
  },
  "source": "string",
  "lot_url": "string",
  "price_sek": "number or null",
  "user_taste_profile": {
    "favorite_designers": ["string"],
    "preferred_eras": ["string"],
    "preferred_materials": ["string"],
    "furniture_type_preferences": ["string"]
  }
}
```

## Output Schema

```json
{
  "taste_score": "number (0.0-1.0)",
  "designer_similarity": "number (0.0-1.0)",
  "visual_quality": "number (0.0-1.0)",
  "material_fit": "number (0.0-1.0)",
  "era_fit": "number (0.0-1.0)",
  "user_behavior_match": "number (0.0-1.0)",
  "novelty_factor": "number (0.0-1.0)",
  "aesthetic_commentary": "string (1-3 sentences about visual appeal)",
  "why_interesting": ["string"],
  "recommendation": "string (must_see|interesting|pass)",
  "reasoning": "string"
}
```

## Component Scores

### 1. Designer Similarity (35% weight)

**High (0.8-1.0)**:
- Direct match to favorite designer
- Same studio/producer as favorite designers
- Known collaborator with curated taste

**Medium (0.5-0.8)**:
- Adjacent designer in same national/stylistic movement
- Similar design philosophy/form language
- Peer of favorite designer

**Low (0.0-0.5)**:
- Different era or aesthetic direction
- Generic period furniture
- Non-designer maker

**Null Matching**:
- If user has no taste profile, evaluate based on canonical importance in Scandinavian Modern canon

### 2. Visual Quality (20% weight)

Assess images for:
- **Proportion & Harmony**: Balanced form, skilled composition
- **Material Expression**: Is the material used authentically? (e.g., teak grain visible, not painted over)
- **Craftmanship**: Visible joinery, finish quality, attention to detail
- **Distinctiveness**: Does it stand out from generic period work?
- **Condition**: How well has it aged? Patina can be a feature

**Scoring**:
- 0.9-1.0: Exemplary craftsmanship, distinctive form, excellent presentation
- 0.7-0.9: Good design and finish, typical of maker quality
- 0.5-0.7: Competent but not exceptional; generic execution
- 0.0-0.5: Poor condition, uninspired design, or unclear images

### 3. Material Fit (15% weight)

Score based on:
- **Alignment with Scandinavian Modern canon**: Teak, rosewood, natural leather preferred
- **Quality**: Premium materials (teak) > common materials (pine)
- **Authentic use**: Natural finishes > stains/paints that hide grain
- **User preferences**: Match to stated material preferences

**Scoring**:
- 0.9-1.0: Teak or rosewood, authentic finish, iconic pairing
- 0.7-0.9: Quality hardwood, good finish, typical of era
- 0.5-0.7: Mixed materials, fabric upholstery, acceptable
- 0.0-0.5: Cheap materials, degraded, artificial finishes

### 4. Era Fit (15% weight)

**High (0.8-1.0)**:
- Falls within "golden age" of Scandinavian Modern (1945-1975)
- Strong match to user era preferences
- Peak period for specific designer

**Medium (0.5-0.8)**:
- Adjacent decades (1930s-1980s)
- Transitional styles
- Emerging designer

**Low (0.0-0.5)**:
- Too early (pre-1930) or too late (post-1980)
- Misalignment with user preferences
- Retro reproduction

### 5. User Behavior Match (10% weight)

If user profile available, score alignment:
- Previous purchases/marked items
- Watched searches
- Time spent on similar lots
- Completion rate on similar categories

**Scoring**:
- 0.8-1.0: Strong alignment, user likely to engage
- 0.5-0.8: Moderate alignment
- 0.0-0.5: Poor fit or no profile data

### 6. Novelty Bonus (5% weight)

Does the piece offer something new/unexpected?
- Rare model or variant
- Lesser-known designer (adjacent list)
- Unusual material combination
- Recently rediscovered maker

**Scoring**:
- 0.5-1.0: Adds novelty value
- 0.0: Seen it before, obvious choice

## Composite Score Calculation

```
taste_score = (
  0.35 × designer_similarity +
  0.20 × visual_quality +
  0.15 × material_fit +
  0.15 × era_fit +
  0.10 × user_behavior_match +
  0.05 × novelty_factor
)
```

## Recommendation Logic

```python
if taste_score >= 0.75:
    recommendation = "must_see"
elif taste_score >= 0.5:
    recommendation = "interesting"
else:
    recommendation = "pass"
```

## Qualitative Assessment

**"Why Interesting" Examples**:
- "Rare production variant of famous Jacobsen design"
- "Teak example in excellent original condition with minimal restoration"
- "Exemplary proportions and material expression"
- "Scarce producer associated with high-quality craftsmanship"
- "Excellent condition for age; patina suggests authentic vintage character"

**Aesthetic Commentary**:
- 1-3 sentences capturing the visual essence
- Reference specific design elements
- Compare favorably to known works if applicable
- Note condition/authenticity

## Failure Convention

If insufficient images or data:

```json
{
  "taste_score": null,
  "recommendation": "pass",
  "reasoning": "Cannot evaluate taste without images or sufficient description"
}
```

## Example Scenario

**Input**:
- Title: "Arne Jacobsen Egg Chair, Fritz Hansen, c.1960"
- Images: Good quality, shows silhouette and condition
- Condition: Very good (light patina on leather)
- Material: Aniline leather on molded fiberglass
- User taste: Loves Jacobsen, prefers 1950s-1960s, leather upholstery preferred

**Evaluation**:
- Designer similarity: 1.0 (exact match, favorite designer)
- Visual quality: 0.85 (excellent design, good condition, iconic form)
- Material fit: 0.90 (aniline leather, authentic Egg construction)
- Era fit: 0.95 (peak Jacobsen/Fritz Hansen period)
- User behavior match: 1.0 (direct favorite match)
- Novelty factor: 0.3 (Egg Chair is well-known, not rare)

**Calculation**:
```
taste_score = (0.35 × 1.0) + (0.20 × 0.85) + (0.15 × 0.90) +
              (0.15 × 0.95) + (0.10 × 1.0) + (0.05 × 0.3)
            = 0.35 + 0.17 + 0.135 + 0.1425 + 0.10 + 0.015
            = 0.9475
```

**Output**:
```json
{
  "taste_score": 0.95,
  "recommendation": "must_see",
  "aesthetic_commentary": "Exemplary Jacobsen Egg Chair in original aniline leather with patina that speaks to authentic vintage character. Proportions and form language are iconic—this represents the pinnacle of 1960s organic modernism.",
  "why_interesting": [
    "Direct match to favorite designer (Arne Jacobsen)",
    "Fritz Hansen authentic production",
    "Excellent condition; original leather patina adds authenticity",
    "Peak era (1960s) for this iconic design"
  ]
}
```

## Related Configuration

- Scoring weights: `config/scoring.yaml` (taste.weights, taste.thresholds)
- Designer seed list: `config/designers.yaml`
