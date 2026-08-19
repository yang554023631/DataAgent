#!/usr/bin/env python3
"""Debug script to see what LLM returns with json_schema mode for COT"""

import sys
import asyncio
import json
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')

from src.intent.llm_client import get_intent_llm_client
from src.analysis.models import AnalysisPlanResult
from src.analysis.prompts import COT_SYSTEM_PROMPT, build_cot_user_prompt, build_field_context_section

# Test case 1: "id为6的广告主4月份的消耗趋势"
field_context = {
    "advertiser_ids": ["6"],
    "time_range": {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "granularity": "day"
    },
    "target_level": "advertiser",
    "metrics": ["cost"]
}

user_prompt = build_cot_user_prompt(
    user_query="id为6的广告主4月份的消耗趋势",
    field_context=field_context,
    advertisers=[],
    few_shot_examples=[]
)

from datetime import date
today_str = date.today().isoformat()
system_prompt = COT_SYSTEM_PROMPT.replace("{today_date}", today_str)

async def debug():
    print("=== Calling LLM with json_schema mode for COT ===")
    print(f"\nSystem prompt length: {len(system_prompt)} chars")
    print(f"\nUser prompt:\n{user_prompt[:500]}...")

    client = get_intent_llm_client()
    response = await client.call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        schema=AnalysisPlanResult
    )

    print("\n=== LLM RAW RESPONSE ===")
    print(repr(response))
    print("\n=== END ===")

    # Try to parse it
    try:
        import json
        parsed = json.loads(response)
        print(f"\n✅ JSON parse OK")
        print(f"  Keys: {list(parsed.keys())}")
        if 'filter_plan' in parsed:
            fp = parsed['filter_plan']
            print(f"  filter_plan keys: {list(fp.keys())}")
            if 'filter_type' in fp:
                print(f"  filter_type: {fp['filter_type']}")
            if 'target_level' in fp:
                print(f"  target_level: {fp['target_level']}")
    except Exception as e:
        print(f"\n❌ JSON parse failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug())
