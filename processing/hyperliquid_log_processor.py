
import requests
from typing import List, Dict, Any, Optional
from eth_abi import decode
from eth_utils import big_endian_to_int
from action_constants import ACTION_SPECS, ACTION_FORMATTED, ACTION_NAMES

# Processing of the logs for the CoreWriter Contract
class CoreWriterLogProcessor:
    
    def __init__(
        self,
        rpc_url: str = "https://g.w.lavanet.xyz:443/gateway/hyperliquid/rpc-http/6c10c96a896dc91d8aa317f9d488ad01",
        contract_address: str = "0x3333333333333333333333333333333333333333",
    ):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
    
    def rpc(self, method: str, params: List[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        response = requests.post(self.rpc_url, json=payload)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            raise Exception(f"RPC error: {result['error']}")
        return result["result"]
    
    def get_current_block(self) -> int:
        block_hex = self.rpc("eth_blockNumber", [])
        return int(block_hex, 16)
    
    def get_logs(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        params = [{
            "address": self.contract_address,
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block)
        }]
        return self.rpc("eth_getLogs", params)
    
    def extract_action_selector_from_log(self, log_hex: str) -> tuple[int, int, bytes]:
        if log_hex.startswith("0x"):
            log_hex = log_hex[2:]
        
        data = bytes.fromhex(log_hex)
        (inner_bytes,) = decode(['bytes'], data)
        
        version = inner_bytes[0]
        action_id = big_endian_to_int(inner_bytes[1:4])
        remaining = inner_bytes[4:]
        
        return version, action_id, remaining
    
    def decode_action(self, log_hex: str) -> Dict[str, Any]:
        version, action_id, payload = self.extract_action_selector_from_log(log_hex)
        
        if action_id not in ACTION_SPECS:
            raise ValueError(f"Unknown action_id: {action_id}")
        
        types = ACTION_SPECS[action_id]
        decoded = decode(types, payload)
        decoded = tuple(decoded)
        formatted = ACTION_FORMATTED.get(action_id)
        if formatted and len(formatted.get("fields", [])) == len(decoded):
            field_dict = {field: value for field, value in zip(formatted["fields"], decoded)}
        else:
            field_dict = {"field_%d" % idx: value for idx, value in enumerate(decoded)}
        
        return {
            "version": version,
            "action_id": action_id,
            "action_name": ACTION_NAMES.get(action_id, "Unknown"),
            "types": types,
            "fields": decoded,
            "field_names": formatted["fields"] if formatted else [],
            "fields_named": field_dict,
            "action_full_name": formatted["action"] if formatted else ACTION_NAMES.get(action_id, "Unknown"),
            "notes": formatted.get("notes", "") if formatted else "",
        }
    
    def process_logs(
        self,
        start_block_height: int,
        end_block_height: int,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        if start_block_height > end_block_height:
            raise ValueError("start_block_height must be <= end_block_height")
        
        all_processed_logs = []
        total_logs = 0
        action_counts = {}
        current_block = start_block_height
        
        while current_block <= end_block_height:
            batch_end = min(current_block + batch_size - 1, end_block_height)
            
            try:
                logs = self.get_logs(current_block, batch_end)
                total_logs += len(logs)
                
                for log in logs:
                    try:
                        decoded = self.decode_action(log['data'])
                        decoded['block_number'] = int(log.get('blockNumber', '0x0'), 16)
                        decoded['transaction_hash'] = log.get('transactionHash')
                        decoded['log_index'] = int(log.get('logIndex', '0x0'), 16)
                        decoded['address'] = log.get('address')
                        decoded['topics'] = log.get('topics', [])
                        
                        all_processed_logs.append(decoded)
                        action_name = decoded['action_name']
                        action_counts[action_name] = action_counts.get(action_name, 0) + 1
                        
                    except Exception as e:
                        print(f"Error decoding log at block {current_block}: {e}")
                        continue
                
                print(f"Processed blocks {current_block} to {batch_end}: {len(logs)} logs")
                
            except Exception as e:
                print(f"Error fetching logs for blocks {current_block} to {batch_end}: {e}")
                pass
            
            current_block = batch_end + 1
        
        return {
            "start_block": start_block_height,
            "end_block": end_block_height,
            "total_logs": total_logs,
            "processed_logs": len(all_processed_logs),
            "action_counts": action_counts,
            "logs": all_processed_logs,
            "action_fields": {
                aid: ACTION_FORMATTED[aid]["fields"]
                for aid in ACTION_FORMATTED
            },
        }

def process_logs(
    start_block_height: int,
    end_block_height: int,
    rpc_url: Optional[str] = None,
    contract_address: Optional[str] = None,
    batch_size: int = 1000
) -> Dict[str, Any]:
    processor = CoreWriterLogProcessor(
        rpc_url=rpc_url,
        contract_address=contract_address
    )
    return processor.process_logs(start_block_height, end_block_height, batch_size)

if __name__ == "__main__":
    print("Fetching logs from block 0x1263528 to 0x1265c38...")

    processor = CoreWriterLogProcessor()
    start_block = 0x1263528
    end_block = 0x1265c38
    batch_size = 1000

    result = processor.process_logs(
        start_block,
        end_block,
        batch_size=batch_size
    )

    print(f"\nProcessing complete!")
    print(f"Blocks: {hex(result['start_block'])} to {hex(result['end_block'])}")
    print(f"Total logs: {result['total_logs']}")
    print(f"Processed logs: {result['processed_logs']}")
    print(f"\nAction counts:")
    for action, count in sorted(result['action_counts'].items()):
        print(f"  {action}: {count}")

    print(f"\nAvailable fields for each action_id:")
    for aid, fields in result.get("action_fields", {}).items():
        print(f"  {aid}: {fields}")

    for log in result['logs']:
        print(log)
