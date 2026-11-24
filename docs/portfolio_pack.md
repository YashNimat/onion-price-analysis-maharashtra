# Portfolio pack: resume, LinkedIn and interview prep

## Resume bullets (pick 3)
- Built an end-to-end analytics project (Python, SQL, Excel, Power BI) on 7,426 mandi price records from 40 Maharashtra markets, testing whether storing onions beats selling immediately after spoilage and storage costs.
- Found that storing for 12 weeks beat selling immediately in only 21% of start weeks (median outcome -45%), with a break-even price rise of about 3.9% per week; flagged a +232% model forecast as unreliable instead of recommending it.
- Backtested naive, seasonal-naive and Holt-Winters forecasts (7.7% vs 19.1% vs 40.0% error), and wrote SQL window-function analysis for seasonality, year-on-year change and market premiums.
- Designed a 5-page Power BI dashboard and an Excel what-if model with a scenario mode; documented data preparation, sample sizes and limitations on a dedicated Methods page.

## LinkedIn post (edit to your voice)
I asked a simple question with Maharashtra onion price data: **is storing onions worth it?**

Prices swung 10x in 2020 (Rs 571 to Rs 5,686 per quintal). But once you count spoilage and storage cost, storing needs prices to rise about 3.9% every week just to break even. In 2020-22, that happened in only 21% of 12-week windows. The typical outcome was -45%.

My forecast model predicted a 232% rise, and I labelled it unreliable. Only 2.6 years of data, a huge 2020 spike, and a calm test period meant it proved nothing about spikes.

Built with Python, SQL, Excel and Power BI. Data: NHRDF (MIT licence). Spoilage and storage figures from ICAR sources.

Repo and dashboard: [link]
#DataAnalytics #PowerBI #Python #SQL

## 2-minute pitch
1. **Question:** Is storing onions worth it after spoilage and storage costs?
2. **Data:** 7,426 prices, 40 Maharashtra markets, Jan 2020 to Jul 2022. The main cleaning work was inconsistent market names.
3. **Finding:** storing beat selling in 21% of weeks; typical outcome -45%.
4. **Honesty:** my forecast said +232%, so I tested it, found the test period was calm and the history short, and labelled it unreliable.
5. **Limits:** data ends in 2022; two full years for seasonality; associations, not causes.

## Likely interview questions
- **Why flag outliers instead of deleting them?** A spike can be real. Only 2 rows were flagged, and I kept them.
- **Why compare against a naive baseline?** A model that can't beat "same as last week" adds nothing. Holt-Winters did beat it, but only on a calm period.
- **Why did the plain Lal vs Unhali average disagree with the same-week comparison?** Plain averages compare different time periods. I compared them at the same market in the same week.
- **Why do you say the arrivals effect is weak?** The 95% interval (-0.6% to 0.0%) includes zero and p = 0.059.
- **What would you do next?** Add recent data (2023 onwards), rainfall, and policy events, then re-test the 12-week rule.
- **What is the weakest part?** The forecast, because of short history. That's why the dashboard says so.
