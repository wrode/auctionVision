# Arbitrage Agent Prompt v1

## Purpose

Determine if a lot represents a good arbitrage opportunity—specifically, whether it can be purchased in Sweden (Auctionet) and profitably resold in Norway or other markets.

## Input Schema

```json
{
  "lot_id": "string",
  "title": "string",
  "description": "string",
  "hammer_price_sek": "number",
  "buyer_premium_sek": "number",
  "total_cost_sek": "number (hammer + premium + VAT)",
  "furniture_type": "string",
  "materials": ["string"],
  "condition": "string",
  "attribution": {
    "primary_designer": "string or null",
    "confidence": "number"
  },
  "source": "string",
  "lot_url": "string"
}
```

## Output Schema

```json
{
  "arbitrage_score": "number (0.0-1.0)",
  "norway_gap_score": "number (0.0-1.0)",
  "norway_gap_label": "string (strong|moderate|weak|none)",
  "estimated_resale_price_nok": "number",
  "estimated_resale_price_sek": "number",
  "gross_margin": "number (0.0-1.0)",
  "net_margin_after_costs": "number (0.0-1.0)",
  "transport_cost_sek": "number",
  "restoration_cost_sek": "number",
  "import_duties_sek": "number",
  "break_even_analysis": {
    "break_even_resale_price_sek": "number",
    "required_markup": "number (multiplier)"
  },
  "recommendation": "string (strong_buy|buy|hold|pass)",
  "key_risks": ["string"],
  "reasoning": "string"
}
```

## Confidence Scoring Guide

**Arbitrage Score** (overall opportunity quality):
- **0.8-1.0**: Strong buy. Price gap significant, low risk, designer authentication confident
- **0.6-0.8**: Buy. Good margin potential, reasonable risk profile
- **0.4-0.6**: Hold. Marginal opportunity, would need perfect resale conditions
- **0.2-0.4**: Pass. Low margin or high risk
- **0.0-0.2**: Avoid. Poor opportunity

**Norway Gap Score** (price differential potential):
- **0.7+**: Strong. Expect 40-100% resale markup
- **0.4-0.7**: Moderate. Expect 20-40% resale markup
- **0.2-0.4**: Weak. Expect <20% markup
- **<0.2**: None. Unlikely to profit

## Evaluation Approach

### 1. Price Foundation

**Formula for Total Acquisition Cost (SEK)**:
```
total_cost_sek = hammer_price + (hammer_price × buyer_premium × (1 + vat_on_premium))
```

From `config/sources.yaml`:
- Auctionet: 22.5% premium + 25% VAT on premium
- Bukowskis: 25% premium + 25% VAT on premium

### 2. Transport Costs (from config/norway_costs.yaml)

Estimate based on furniture_type:
- Small chair: 1,500 SEK
- Standard chair/small table: 3,000 SEK
- Large sofa/table: 5,000 SEK
- Oversized/sectional: 8,000 SEK

### 3. Restoration/Condition Buffer

From config/norway_costs.yaml:
- None needed: 0%
- Minor touch-up: 5% of hammer price
- Moderate restoration: 15% of hammer price
- Significant restoration: 30% of hammer price

### 4. Import/Customs (Norway)

- Antiques (>100 years): May be exempt from customs
- Modern furniture: Typically 0% customs duty, but 25% VAT applies
- Currency conversion: SEK to NOK at ~1.02 rate

### 5. Resale Estimation

**Norway Premium Multiplier** (from config/norway_costs.yaml):
- Well-known designer pieces: 1.3–2.0x acquisition cost
- Strong Nordic Modern: 1.5–1.8x
- Generic period furniture: 1.1–1.3x

Factors:
- **Designer + Attribution Confidence**: High confidence + known designer → higher multiplier
- **Material Quality**: Teak, rosewood → higher premium
- **Condition**: Excellent condition → higher multiplier
- **Rarity**: Scarce models/makers → higher multiplier

**Sale Channel**:
- Dealer sale (30% commission): `resale_price × 0.7`
- Private sale (no commission): Full resale_price
- Use conservative estimate (private sale assumption)

### 6. Margin Calculation

```
gross_resale_sek = estimated_resale_price_nok / 1.02
total_cost = hammer_price + premium_with_vat + transport + restoration + duties
gross_margin = (gross_resale_sek - total_cost) / gross_resale_sek
net_margin = (gross_resale_sek - total_cost - dealer_margin) / gross_resale_sek
```

Break-even:
```
required_resale_price = total_cost / (1 - desired_margin)
required_markup = resale_price / acquisition_price
```

### 7. Risk Factors

**High-Risk Scenarios** (reduce score):
- Attribution confidence < 0.3: May not sell in hoped market
- Condition issues: Restoration cost unpredictable
- Liquidity: Niche designers harder to resell quickly
- Market timing: Seasonal demand variations
- Shipping damage risk: Larger items more fragile

**Low-Risk Scenarios** (boost score):
- Well-known designer (Wegner, Jacobsen, Panton)
- Excellent condition
- Strong designer authentication (0.7+ confidence)
- Proven buyer demand (recent comparable sales)

## Recommendations Logic

```python
if arbitrage_score >= 0.8 and norway_gap_score >= 0.7:
    recommendation = "strong_buy"
elif arbitrage_score >= 0.6 and norway_gap_score >= 0.5:
    recommendation = "buy"
elif arbitrage_score >= 0.4 and norway_gap_score >= 0.3:
    recommendation = "hold"
else:
    recommendation = "pass"
```

## Failure Convention

If prices are missing or resale estimation is impossible:

```json
{
  "arbitrage_score": 0.0,
  "recommendation": "pass",
  "reasoning": "Insufficient pricing data to evaluate arbitrage potential"
}
```

## Example Scenario

**Input**:
- Hammer price: 8,000 SEK
- Buyer premium: 1,800 SEK (22.5%)
- VAT on premium: 450 SEK (25% of premium)
- **Total acquisition cost: 10,250 SEK**
- Furniture: Teak lounge chair
- Condition: Good (minor scratches)
- Attribution: Hans Wegner, confidence 0.75

**Calculations**:
- Transport estimate: 3,000 SEK (medium item)
- Restoration estimate: 400 SEK (5% of 8,000 for minor touchup)
- Import VAT (Norway): 25% of total acquisition = 2,562 SEK
- **Total landed cost in Norway: ~15,812 SEK (~1,550 NOK)**
- Estimated Norway resale (Wegner 1950s teak, good condition): 35,000 NOK (~3,400 SEK)
- Gross margin: (34,000 - 15,812) / 34,000 = 53%

**Output**:
```json
{
  "arbitrage_score": 0.75,
  "norway_gap_score": 0.65,
  "norway_gap_label": "moderate",
  "estimated_resale_price_nok": 35000,
  "gross_margin": 0.53,
  "net_margin_after_costs": 0.42,
  "recommendation": "buy",
  "reasoning": "Well-authenticated Wegner piece with moderate Norway premium; 42% net margin after all costs and conservatively assumes private sale."
}
```

## Related Configuration

- Cost assumptions: `config/norway_costs.yaml`
- Source-specific buyer premiums: `config/sources.yaml`
- Scoring thresholds: `config/scoring.yaml` (arbitrage.thresholds)
- Scoring weights: `config/scoring.yaml` (arbitrage.weights)
