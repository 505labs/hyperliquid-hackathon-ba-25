"""
Hyperliquid Vault MCP Server
MCP server for analyzing vault deposit/withdrawal activity.
"""

import os
import sys
import time
import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

# Import functions from log processor
try:
    from hyperliquid_log_processor import get_vault_transfers, get_delegations
except ImportError:
    # Fallback if import fails
    def get_vault_transfers() -> List[Dict[str, Any]]:
        return []
    def get_delegations() -> List[Dict[str, Any]]:
        return []

# Setup logging - goes to stderr (safe for stdio MCP servers)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Helper function for debug prints (goes to stderr)
def debug_print(*args, **kwargs):
    """Print to stderr for debugging (safe for MCP stdio transport)."""
    print(*args, **kwargs, file=sys.stderr, flush=True)

# Create an MCP server
mcp = FastMCP("Hyperliquid Vault Server")

# Hardcoded list of known vault addresses
# TODO: This should be populated from actual on-chain data or configuration
KNOWN_VAULT_ADDRESSES = [
    "0x1234567890123456789012345678901234567890",
    "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    "0x9876543210987654321098765432109876543210",
]


def format_response(
    data: Any,
    execution_time_ms: float = 0,
    errors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Format response according to spec."""
    return {
        "success": errors is None or len(errors) == 0,
        "data": data,
        "metadata": {
            "execution_time": execution_time_ms,
        },
        "errors": errors if errors else None
    }


# ============================================================================
# Vault Tools
# ============================================================================

@mcp.tool()
def list_vault_addresses() -> Dict[str, Any]:
    """
    Get list of all known vault addresses.
    Returns hardcoded list of vault addresses that can be monitored.
    """
    start_time = time.time()
    errors = []
    data = {}
    
    try:
        debug_print(f"[list_vault_addresses] Fetching vault addresses...")
        
        # Get vault transfers to extract unique vault addresses
        vault_transfers = get_vault_transfers()
        
        # Extract unique vault addresses from transfers
        vault_addresses_from_transfers = set()
        for transfer in vault_transfers:
            vault_addr = transfer.get("vault", "").lower()
            if vault_addr:
                vault_addresses_from_transfers.add(vault_addr)
        
        # Combine hardcoded addresses with addresses from transfers
        all_vaults = set(KNOWN_VAULT_ADDRESSES)
        for addr in vault_addresses_from_transfers:
            all_vaults.add(addr)
        
        # Convert to list and normalize
        vault_list = [addr.lower() if addr.startswith("0x") else f"0x{addr}" for addr in all_vaults]
        vault_list.sort()  # Sort for consistency
        
        data = {
            "vaults": vault_list,
            "total_count": len(vault_list),
            "from_hardcoded": len(KNOWN_VAULT_ADDRESSES),
            "from_transfers": len(vault_addresses_from_transfers),
            "hardcoded_addresses": [addr.lower() for addr in KNOWN_VAULT_ADDRESSES],
        }
        
        debug_print(f"[list_vault_addresses] Found {len(vault_list)} vault addresses")
        
    except Exception as e:
        error_msg = str(e)
        errors.append(error_msg)
        logger.error(f"Error listing vault addresses: {error_msg}", exc_info=True)
        data = {"vaults": [], "total_count": 0}
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, execution_time, errors if errors else None)


@mcp.tool()
def get_vault_activity(
    vault_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get deposit/withdrawal activity for vault(s).
    
    Args:
        vault_address: Optional specific vault address. If not provided, returns activity for all vaults.
    
    Returns:
        Number of deposits/withdrawals and total amounts for each vault.
    """
    start_time = time.time()
    errors = []
    data = {}
    
    try:
        debug_print(f"[get_vault_activity] Fetching vault activity...")
        if vault_address:
            debug_print(f"[get_vault_activity] Filtering for vault: {vault_address}")
        
        # Get vault transfers from log processor
        vault_transfers = get_vault_transfers()
        debug_print(f"[get_vault_activity] Retrieved {len(vault_transfers)} vault transfers")
        
        # Process transfers by vault
        vault_stats = defaultdict(lambda: {
            "vault": "",
            "deposit_count": 0,
            "withdrawal_count": 0,
            "total_deposits_usd": 0,
            "total_withdrawals_usd": 0,
            "net_flow_usd": 0,
            "transfers": []
        })
        
        for transfer in vault_transfers:
            vault_addr = transfer.get("vault", "").lower()
            if not vault_addr:
                continue
            
            # Normalize address
            if not vault_addr.startswith("0x"):
                vault_addr = "0x" + vault_addr
            
            # Filter by specific vault if requested
            if vault_address:
                vault_address_normalized = vault_address.lower()
                if not vault_address_normalized.startswith("0x"):
                    vault_address_normalized = "0x" + vault_address_normalized
                if vault_addr != vault_address_normalized:
                    continue
            
            is_deposit = transfer.get("isDeposit", False)
            usd_amount = transfer.get("usd", 0)
            
            # Ensure usd_amount is an integer
            if isinstance(usd_amount, str):
                # Try to convert hex string
                if usd_amount.startswith("0x"):
                    usd_amount = int(usd_amount, 16)
                else:
                    usd_amount = int(usd_amount)
            
            stats = vault_stats[vault_addr]
            stats["vault"] = vault_addr
            
            if is_deposit:
                stats["deposit_count"] += 1
                stats["total_deposits_usd"] += usd_amount
            else:
                stats["withdrawal_count"] += 1
                stats["total_withdrawals_usd"] += usd_amount
            
            # Calculate net flow
            stats["net_flow_usd"] = stats["total_deposits_usd"] - stats["total_withdrawals_usd"]
            
            # Store transfer details
            stats["transfers"].append({
                "isDeposit": is_deposit,
                "usd": usd_amount,
                "usd_formatted": usd_amount / 1e18 if usd_amount > 0 else 0  # Assuming 18 decimals
            })
        
        # Convert to list format
        vault_activities = []
        for vault_addr, stats in vault_stats.items():
            vault_activities.append({
                "vault": stats["vault"],
                "deposit_count": stats["deposit_count"],
                "withdrawal_count": stats["withdrawal_count"],
                "total_deposits_usd": stats["total_deposits_usd"],
                "total_deposits_usd_formatted": stats["total_deposits_usd"] / 1e18,
                "total_withdrawals_usd": stats["total_withdrawals_usd"],
                "total_withdrawals_usd_formatted": stats["total_withdrawals_usd"] / 1e18,
                "net_flow_usd": stats["net_flow_usd"],
                "net_flow_usd_formatted": stats["net_flow_usd"] / 1e18,
                "transfer_count": len(stats["transfers"])
            })
        
        # Sort by net flow (most positive first)
        vault_activities.sort(key=lambda x: x["net_flow_usd"], reverse=True)
        
        # Calculate totals
        total_deposits = sum(v["total_deposits_usd"] for v in vault_activities)
        total_withdrawals = sum(v["total_withdrawals_usd"] for v in vault_activities)
        total_transfers = sum(v["transfer_count"] for v in vault_activities)
        
        data = {
            "vaults": vault_activities,
            "summary": {
                "total_vaults": len(vault_activities),
                "total_deposits_usd": total_deposits,
                "total_deposits_usd_formatted": total_deposits / 1e18,
                "total_withdrawals_usd": total_withdrawals,
                "total_withdrawals_usd_formatted": total_withdrawals / 1e18,
                "total_transfers": total_transfers,
                "net_flow_usd": total_deposits - total_withdrawals,
                "net_flow_usd_formatted": (total_deposits - total_withdrawals) / 1e18
            },
            "filtered_by_vault": vault_address is not None,
            "vault_address_filter": vault_address.lower() if vault_address else None
        }
        
        debug_print(f"[get_vault_activity] Processed {len(vault_activities)} vault(s)")
        if vault_address:
            debug_print(f"[get_vault_activity] Filtered for vault: {vault_address}")
        
    except Exception as e:
        error_msg = str(e)
        errors.append(error_msg)
        logger.error(f"Error getting vault activity: {error_msg}", exc_info=True)
        data = {"vaults": [], "summary": {}}
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, execution_time, errors if errors else None)


@mcp.tool()
def get_delegation_info() -> Dict[str, Any]:
    """
    Get delegation information aggregated by validator address.
    Returns count of delegations and undelegations for each validator.
    
    Returns:
        Aggregated delegation statistics per validator address.
    """
    start_time = time.time()
    errors = []
    data = {}
    
    try:
        debug_print(f"[get_delegation_info] Fetching delegation data...")
        
        # Get delegations from log processor
        delegations = get_delegations()
        debug_print(f"[get_delegation_info] Retrieved {len(delegations)} delegation records")
        
        # Aggregate by validator address
        validator_stats = defaultdict(lambda: {
            "validator": "",
            "delegation_count": 0,
            "undelegation_count": 0,
            "total_delegated_wei": 0,
            "total_undelegated_wei": 0,
            "net_delegated_wei": 0,
            "delegations": []
        })
        
        for delegation in delegations:
            validator_addr = delegation.get("validator", "").lower()
            if not validator_addr:
                continue
            
            # Normalize address
            if not validator_addr.startswith("0x"):
                validator_addr = "0x" + validator_addr
            
            is_undelegate = delegation.get("isUndelegate", False)
            wei_amount = delegation.get("wei", 0)
            
            # Ensure wei_amount is an integer
            if isinstance(wei_amount, str):
                # Try to convert hex string
                if wei_amount.startswith("0x"):
                    wei_amount = int(wei_amount, 16)
                else:
                    wei_amount = int(wei_amount)
            
            stats = validator_stats[validator_addr]
            stats["validator"] = validator_addr
            
            if is_undelegate:
                stats["undelegation_count"] += 1
                stats["total_undelegated_wei"] += wei_amount
            else:
                stats["delegation_count"] += 1
                stats["total_delegated_wei"] += wei_amount
            
            # Calculate net delegated (delegated - undelegated)
            stats["net_delegated_wei"] = stats["total_delegated_wei"] - stats["total_undelegated_wei"]
            
            # Store delegation details
            stats["delegations"].append({
                "isUndelegate": is_undelegate,
                "wei": wei_amount,
                "wei_formatted": wei_amount / 1e18 if wei_amount > 0 else 0  # Assuming 18 decimals
            })
        
        # Convert to list format
        validator_activities = []
        for validator_addr, stats in validator_stats.items():
            validator_activities.append({
                "validator": stats["validator"],
                "delegation_count": stats["delegation_count"],
                "undelegation_count": stats["undelegation_count"],
                "total_delegated_wei": stats["total_delegated_wei"],
                "total_delegated_wei_formatted": stats["total_delegated_wei"] / 1e18,
                "total_undelegated_wei": stats["total_undelegated_wei"],
                "total_undelegated_wei_formatted": stats["total_undelegated_wei"] / 1e18,
                "net_delegated_wei": stats["net_delegated_wei"],
                "net_delegated_wei_formatted": stats["net_delegated_wei"] / 1e18,
                "total_operations": stats["delegation_count"] + stats["undelegation_count"]
            })
        
        # Sort by net delegated amount (most delegated first)
        validator_activities.sort(key=lambda x: x["net_delegated_wei"], reverse=True)
        
        # Calculate totals
        total_delegations = sum(v["delegation_count"] for v in validator_activities)
        total_undelegations = sum(v["undelegation_count"] for v in validator_activities)
        total_delegated = sum(v["total_delegated_wei"] for v in validator_activities)
        total_undelegated = sum(v["total_undelegated_wei"] for v in validator_activities)
        total_validators = len(validator_activities)
        
        data = {
            "validators": validator_activities,
            "summary": {
                "total_validators": total_validators,
                "total_delegations": total_delegations,
                "total_undelegations": total_undelegations,
                "total_delegated_wei": total_delegated,
                "total_delegated_wei_formatted": total_delegated / 1e18,
                "total_undelegated_wei": total_undelegated,
                "total_undelegated_wei_formatted": total_undelegated / 1e18,
                "net_delegated_wei": total_delegated - total_undelegated,
                "net_delegated_wei_formatted": (total_delegated - total_undelegated) / 1e18,
                "total_operations": total_delegations + total_undelegations
            }
        }
        
        debug_print(f"[get_delegation_info] Processed {total_validators} validator(s)")
        debug_print(f"[get_delegation_info] Total delegations: {total_delegations}, undelegations: {total_undelegations}")
        
    except Exception as e:
        error_msg = str(e)
        errors.append(error_msg)
        logger.error(f"Error getting delegation info: {error_msg}", exc_info=True)
        data = {"validators": [], "summary": {}}
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, execution_time, errors if errors else None)
