#!/usr/bin/env python3
"""
Simple test script for vault-server MCP tools.
Tests the vault listing and activity functions.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the vault server module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "vault_server",
    os.path.join(os.path.dirname(__file__), "vault-server.py")
)
vault_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vault_server)

# Import functions from log processor
from hyperliquid_log_processor import get_vault_transfers, get_delegations


def test_list_vault_addresses():
    """Test listing vault addresses."""
    print("=" * 60)
    print("Testing: list_vault_addresses")
    print("=" * 60)
    
    result = vault_server.list_vault_addresses()
    
    print(f"Success: {result['success']}")
    print(f"Vaults found: {result['data']['total_count']}")
    print(f"Vault addresses:")
    for vault in result['data']['vaults']:
        print(f"  - {vault}")
    
    print(f"\nExecution time: {result['metadata']['execution_time']:.2f}ms")
    print()
    
    return result


def test_get_vault_activity_all():
    """Test getting activity for all vaults."""
    print("=" * 60)
    print("Testing: get_vault_activity (all vaults)")
    print("=" * 60)
    
    result = vault_server.get_vault_activity()
    
    print(f"Success: {result['success']}")
    print(f"Vaults with activity: {result['data']['summary']['total_vaults']}")
    print(f"Total transfers: {result['data']['summary']['total_transfers']}")
    print(f"Total deposits: {result['data']['summary']['total_deposits_usd_formatted']:.6f} USD")
    print(f"Total withdrawals: {result['data']['summary']['total_withdrawals_usd_formatted']:.6f} USD")
    print(f"Net flow: {result['data']['summary']['net_flow_usd_formatted']:.6f} USD")
    
    print("\nVault details:")
    for vault in result['data']['vaults']:
        print(f"\n  Vault: {vault['vault']}")
        print(f"    Deposits: {vault['deposit_count']} ({vault['total_deposits_usd_formatted']:.6f} USD)")
        print(f"    Withdrawals: {vault['withdrawal_count']} ({vault['total_withdrawals_usd_formatted']:.6f} USD)")
        print(f"    Net flow: {vault['net_flow_usd_formatted']:.6f} USD")
    
    print(f"\nExecution time: {result['metadata']['execution_time']:.2f}ms")
    print()
    
    return result


def test_get_vault_activity_specific():
    """Test getting activity for a specific vault."""
    print("=" * 60)
    print("Testing: get_vault_activity (specific vault)")
    print("=" * 60)
    
    # Get first vault from list
    list_result = vault_server.list_vault_addresses()
    if list_result['data']['vaults']:
        test_vault = list_result['data']['vaults'][0]
        print(f"Testing with vault: {test_vault}")
        
        result = vault_server.get_vault_activity(vault_address=test_vault)
        
        print(f"Success: {result['success']}")
        print(f"Filtered by vault: {result['data']['filtered_by_vault']}")
        print(f"Vaults found: {result['data']['summary']['total_vaults']}")
        
        if result['data']['vaults']:
            vault = result['data']['vaults'][0]
            print(f"\nVault: {vault['vault']}")
            print(f"  Deposits: {vault['deposit_count']} ({vault['total_deposits_usd_formatted']:.6f} USD)")
            print(f"  Withdrawals: {vault['withdrawal_count']} ({vault['total_withdrawals_usd_formatted']:.6f} USD)")
            print(f"  Net flow: {vault['net_flow_usd_formatted']:.6f} USD")
        
        print(f"\nExecution time: {result['metadata']['execution_time']:.2f}ms")
        print()
        
        return result
    else:
        print("No vaults available to test")
        return None


def test_get_delegation_info():
    """Test getting delegation information."""
    print("=" * 60)
    print("Testing: get_delegation_info")
    print("=" * 60)
    
    result = vault_server.get_delegation_info()
    
    print(f"Success: {result['success']}")
    print(f"Validators found: {result['data']['summary']['total_validators']}")
    print(f"Total delegations: {result['data']['summary']['total_delegations']}")
    print(f"Total undelegations: {result['data']['summary']['total_undelegations']}")
    print(f"Total delegated: {result['data']['summary']['total_delegated_wei_formatted']:.6f} ETH")
    print(f"Total undelegated: {result['data']['summary']['total_undelegated_wei_formatted']:.6f} ETH")
    print(f"Net delegated: {result['data']['summary']['net_delegated_wei_formatted']:.6f} ETH")
    
    print("\nValidator details:")
    for validator in result['data']['validators']:
        print(f"\n  Validator: {validator['validator']}")
        print(f"    Delegations: {validator['delegation_count']} ({validator['total_delegated_wei_formatted']:.6f} ETH)")
        print(f"    Undelegations: {validator['undelegation_count']} ({validator['total_undelegated_wei_formatted']:.6f} ETH)")
        print(f"    Net delegated: {validator['net_delegated_wei_formatted']:.6f} ETH")
        print(f"    Total operations: {validator['total_operations']}")
    
    print(f"\nExecution time: {result['metadata']['execution_time']:.2f}ms")
    print()
    
    return result


if __name__ == "__main__":
    print("Vault Server MCP Tools Test")
    print("=" * 60)
    print()
    
    # Test vault transfers function
    print("Testing get_vault_transfers() function...")
    transfers = get_vault_transfers()
    print(f"Retrieved {len(transfers)} vault transfers")
    if transfers:
        print("Sample transfer:")
        print(f"  Vault: {transfers[0].get('vault')}")
        print(f"  Is Deposit: {transfers[0].get('isDeposit')}")
        print(f"  USD: {transfers[0].get('usd')}")
    print()
    
    # Test delegation function
    print("Testing get_delegations() function...")
    delegations = get_delegations()
    print(f"Retrieved {len(delegations)} delegations")
    if delegations:
        print("Sample delegation:")
        print(f"  Validator: {delegations[0].get('validator')}")
        print(f"  Is Undelegate: {delegations[0].get('isUndelegate')}")
        print(f"  Wei: {delegations[0].get('wei')}")
    print()
    
    # Test MCP tools
    try:
        test_list_vault_addresses()
        test_get_vault_activity_all()
        test_get_vault_activity_specific()
        test_get_delegation_info()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

