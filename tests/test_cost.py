import boto3
from dataclasses import dataclass, field
from botocore.exceptions import ClientError

from dotenv import load_dotenv
load_dotenv()  # Load AWS credentials from .env file if present
# ----------------------------------------
# BEDROCK COST CALCULATOR
# ----------------------------------------

@dataclass
class BedrockCostCalculator:
    input_tokens:     int
    output_tokens:    int
    bedrock_model_id: str

    # Computed after init
    input_cost_per_1m:  float = field(init=False, default=0.0)
    output_cost_per_1m: float = field(init=False, default=0.0)
    input_cost:         float = field(init=False, default=0.0)
    output_cost:        float = field(init=False, default=0.0)
    total_cost:         float = field(init=False, default=0.0)

    def __post_init__(self):
        self._fetch_pricing()
        self._calculate()

    # ----------------------------------------
    # PRIVATE: Fetch pricing from AWS Bedrock
    # ----------------------------------------

    def _fetch_pricing(self):
        """
        Fetches cost per 1M input/output tokens
        from AWS Bedrock for the given model ID.
        """
        try:
            client = boto3.client("bedrock", region_name="us-east-1")

            response = client.get_foundation_model(
                modelIdentifier=self.bedrock_model_id
            )

            model_details = response.get("modelDetails", {})
            pricing       = model_details.get("modelPricing", {})

            # Pricing is per 1M tokens
            self.input_cost_per_1m  = float(pricing.get("inputTokenPrice",  0))
            self.output_cost_per_1m = float(pricing.get("outputTokenPrice", 0))

            if self.input_cost_per_1m == 0 or self.output_cost_per_1m == 0:
                raise ValueError(
                    f"Pricing not available for model: '{self.bedrock_model_id}'"
                )

        except ClientError as e:
            raise RuntimeError(f"AWS Bedrock error: {e}")

    # ----------------------------------------
    # PRIVATE: Calculate cost from token counts
    # ----------------------------------------

    def _calculate(self):
        """
        Cost Formula:
            input_cost  = (input_tokens  / 1,000,000) * input_cost_per_1M
            output_cost = (output_tokens / 1,000,000) * output_cost_per_1M
            total_cost  = input_cost + output_cost
        """
        self.input_cost  = (self.input_tokens  / 1_000_000) * self.input_cost_per_1m
        self.output_cost = (self.output_tokens / 1_000_000) * self.output_cost_per_1m
        self.total_cost  = self.input_cost + self.output_cost

    # ----------------------------------------
    # PUBLIC: Get cost breakdown as dict
    # ----------------------------------------

    def get_cost(self) -> dict:
        return {
            "model_id":            self.bedrock_model_id,
            "input_tokens":        self.input_tokens,
            "output_tokens":       self.output_tokens,
            "input_cost_per_1m":   round(self.input_cost_per_1m,  6),
            "output_cost_per_1m":  round(self.output_cost_per_1m, 6),
            "input_cost":          round(self.input_cost,          6),
            "output_cost":         round(self.output_cost,         6),
            "total_cost":          round(self.total_cost,          6),
        }

    # ----------------------------------------
    # PUBLIC: Pretty print summary
    # ----------------------------------------

    def print_summary(self):
        print(f"\n========== BEDROCK COST SUMMARY ==========\n")
        print(f"  Model              : {self.bedrock_model_id}")
        print(f"  Input Tokens       : {self.input_tokens:,}")
        print(f"  Output Tokens      : {self.output_tokens:,}")
        print(f"  Input  per 1M      : ${self.input_cost_per_1m:.4f}")
        print(f"  Output per 1M      : ${self.output_cost_per_1m:.4f}")
        print(f"  Input Cost         : ${self.input_cost:.6f}")
        print(f"  Output Cost        : ${self.output_cost:.6f}")
        print(f"  Total Cost         : ${self.total_cost:.6f}")
        print()


# ----------------------------------------
# MAIN
# ----------------------------------------

if __name__ == "__main__":

    calc = BedrockCostCalculator(
        input_tokens=10_000,
        output_tokens=2_000,
        bedrock_model_id="qwen.qwen3-next-80b-a3b"
    )

    calc.print_summary()
    print(calc.get_cost())