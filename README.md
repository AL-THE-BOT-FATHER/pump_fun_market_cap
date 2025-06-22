# PumpFunMarketCap

A Python module for fetching on-chain bonding-curve data and calculating token price & market cap in both SOL and USD for “Pump Fun” tokens on Solana.

## Features

- Derive and parse the on-chain bonding-curve account for a given token mint
- Fetch virtual SOL and token reserves from the bonding curve
- Retrieve the current SOL→USD price from DIA Oracle
- Calculate:
  - Token price in SOL
  - Token price in USD
  - Token market cap in USD
