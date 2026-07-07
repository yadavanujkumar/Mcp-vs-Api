import asyncio
from typing import Any, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SHIPMENT_ID = "SHP-1001"
MAX_COST_INCREASE_PCT = 15.0


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    raise ValueError(f"Unexpected structured value: {type(value)!r}")


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return value
    raise ValueError(f"Unexpected list value: {type(value)!r}")


async def mitigate_incident() -> None:
    server_params = StdioServerParameters(command="python", args=["supply_chain_mcp_server.py"], env={})

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Discovered tools:", [tool.name for tool in tools.tools])

            shipment_response = await session.call_tool(
                "inspect_delayed_shipment",
                {"shipment_id": SHIPMENT_ID},
            )
            shipment = _as_dict(shipment_response.structured_content or shipment_response.content)
            print("Shipment:", shipment)

            if shipment["status"] != "DELAYED":
                print("No mitigation needed: shipment is not delayed.")
                return

            options_response = await session.call_tool(
                "find_alternate_vendor",
                {
                    "lane_origin": shipment["origin"],
                    "lane_destination": shipment["destination"],
                    "max_cost_increase_pct": MAX_COST_INCREASE_PCT,
                },
            )
            options = _as_list(options_response.structured_content or options_response.content)

            if not options:
                print("No compliant alternate vendors found.")
                return

            best_option = options[0]
            reason = (
                f"Auto mitigation for delayed shipment {SHIPMENT_ID}; "
                f"selected {best_option['vendor_id']} ETA={best_option['predicted_eta_hours']}h "
                f"cost_delta={best_option['incremental_cost_pct']}%."
            )

            reroute_response = await session.call_tool(
                "execute_reroute",
                {
                    "shipment_id": SHIPMENT_ID,
                    "new_vendor_id": best_option["vendor_id"],
                    "reason": reason,
                },
            )
            reroute_result = reroute_response.structured_content or reroute_response.content
            print("Reroute result:", reroute_result)


if __name__ == "__main__":
    asyncio.run(mitigate_incident())
