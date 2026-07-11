import boto3
import json
import logging
import os
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from typing import Tuple, Dict, Optional, List
from dotenv import load_dotenv

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BedrockDynamicCostCalculator:
    """
    Fetches all models and pricing dynamically from AWS Bedrock and Pricing APIs.
    Strictly NO hardcoded model IDs or fallback prices.
    """

    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.bedrock_client = boto3.client("bedrock", region_name=self.region_name)
        # The AWS Pricing API endpoint itself is typically only available in us-east-1
        self.pricing_client = boto3.client("pricing", region_name="us-east-1")
        self.catalog: List[dict] = []
        self.pricing_map: Dict[str, Tuple[float, float]] = {}
        self._init_catalog()

    def _init_catalog(self):
        try:
            for svc in ["AmazonBedrock", "AmazonBedrockService"]:
                paginator = self.pricing_client.get_paginator('get_products')
                for page in paginator.paginate(
                    ServiceCode=svc,
                    Filters=[{"Type": "TERM_MATCH", "Field": "regionCode", "Value": self.region_name}],
                    FormatVersion="aws_v1",
                ):
                    for price_str in page.get("PriceList", []):
                        self.catalog.append(json.loads(price_str))
            logger.info(f"Loaded {len(self.catalog)} pricing items from AWS Pricing API.")
        except Exception as e:
            logger.warning(f"Failed to load AWS pricing catalog: {e}")

    def _extract_price(self, item: dict) -> float:
        terms = item.get("terms", {}).get("OnDemand", {})
        for sku in terms.values():
            for dim in sku.get("priceDimensions", {}).values():
                rate = float(dim.get("pricePerUnit", {}).get("USD", 0))
                unit = dim.get("unit", "").lower()
                if rate > 0:
                    return rate * 1000 if "1k" in unit else rate
        return 0.0

    def get_all_models_pricing(self) -> Dict[str, Tuple[float, float]]:
        """
        Fetch all foundation models and map them to their pricing dynamically.
        Returns a dictionary mapping model_id to (input_price, output_price).
        """
        try:
            models = self.bedrock_client.list_foundation_models()["modelSummaries"]
        except Exception as e:
            logger.error(f"Failed to list foundation models: {e}")
            return {}

        result = {}
        for model in models:
            model_id = model["modelId"]
            model_name = model.get("modelName", "")
            
            # Find input and output prices in the catalog
            input_price = None
            output_price = None
            
            for item in self.catalog:
                attrs = item.get("product", {}).get("attributes", {})
                
                # Match logic: check modelId exact match, or model name exact match
                match_id = attrs.get("modelId") == model_id
                match_name = attrs.get("model") == model_name and model_name
                # Some usagetypes contain the model id without punctuation
                usagetype = attrs.get("usagetype", "").lower()
                match_usage = model_id.lower().replace(".", "").replace("-", "") in usagetype.replace("-", "")

                if match_id or match_name or match_usage:
                    inf_type = attrs.get("inferenceType", "").lower()
                    price = self._extract_price(item)
                    
                    if price > 0:
                        if "input" in inf_type and "output" not in inf_type:
                            input_price = price if input_price is None else min(input_price, price)
                        elif "output" in inf_type and "input" not in inf_type:
                            output_price = price if output_price is None else min(output_price, price)

            # Default to 0.0 if not found in AWS API
            in_p = input_price or 0.0
            out_p = output_price or 0.0
            
            result[model_id] = (in_p, out_p)
            
        self.pricing_map = result
        return result

    def calculate_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        """
        Calculate the total USD cost for a given number of input and output tokens.
        Automatically loads the pricing map if it hasn't been loaded yet.
        """
        if not self.pricing_map:
            self.get_all_models_pricing()
            
        prices = self.pricing_map.get(model_id)
        if not prices:
            logger.warning(f"No pricing found for model '{model_id}', assuming $0.00")
            return 0.0
            
        input_per_1M, output_per_1M = prices
        total_cost = (input_tokens / 1_000_000) * input_per_1M + (output_tokens / 1_000_000) * output_per_1M
        return round(total_cost, 6)

if __name__ == "__main__":
    calc = BedrockDynamicCostCalculator()
    
    # # Example 1: Show all prices
    # prices = calc.get_all_models_pricing()
    # print(f"\n{'MODEL ID':<50} {'INPUT/1M':<10} {'OUTPUT/1M':<10}")
    # print("-" * 75)
    # for m_id, (in_cost, out_cost) in sorted(prices.items()):
    #     if in_cost > 0 or out_cost > 0:
    #         print(f"{m_id:<50} ${in_cost:<9.6f} ${out_cost:<9.6f}")

    # Example 2: Calculate specific cost
    print("\n" + "="*75)
    test_model = os.getenv("BEDROCK_MODEL_ID", "")
    in_tok = 2500
    out_tok = 800
    
    cost = calc.calculate_cost(
        input_tokens=in_tok,
        output_tokens=out_tok,
        model_id=test_model
    )
    print(f"Cost Calculation Test:")
    print(f"Model:  {test_model}")
    print(f"Input:  {in_tok} tokens")
    print(f"Output: {out_tok} tokens")
    print(f"Total:  ${cost:.6f}")
    print("="*75 + "\n")