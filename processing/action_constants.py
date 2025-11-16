"""
Action constants for Hyperliquid log processing.
Contains action specifications, formatted descriptions, and name mappings.
"""

# Action specifications for decoding
ACTION_SPECS = {
    1: ["uint32", "bool", "uint64", "uint64", "bool", "uint8", "uint128"],
    2: ["address", "bool", "uint64"],
    3: ["address", "uint64", "bool"],
    4: ["uint64"],
    5: ["uint64"],
    6: ["address", "uint64", "uint64"],
    7: ["uint64", "bool"],
    8: ["uint64", "uint8", "uint64"],
    9: ["address", "string"],
    10: ["uint32", "uint64"],
    11: ["uint32", "uint128"],
    12: ["uint64", "address"],
    13: ["address", "address", "uint32", "uint32", "uint64", "uint64"],
    14: ["uint64", "uint64", "bool"],
}

ACTION_FORMATTED = {
    1: {
        "action": "Limit order",
        "fields": ["asset", "isBuy", "limitPx", "sz", "reduceOnly", "encodedTif", "cloid"],
        "notes": "Tif: 1=Alo, 2=Gtc, 3=Ioc. Cloid 0 = none; otherwise a unique ID. limitPx & sz use 1e8 scaling."
    },
    2: {
        "action": "Vault transfer",
        "fields": ["vault", "isDeposit", "usd"],
        "notes": ""
    },
    3: {
        "action": "Token delegate",
        "fields": ["validator", "wei", "isUndelegate"],
        "notes": ""
    },
    4: {
        "action": "Staking deposit",
        "fields": ["wei"],
        "notes": ""
    },
    5: {
        "action": "Staking withdraw",
        "fields": ["wei"],
        "notes": ""
    },
    6: {
        "action": "Spot send",
        "fields": ["destination", "token", "wei"],
        "notes": ""
    },
    7: {
        "action": "USD class transfer",
        "fields": ["ntl", "toPerp"],
        "notes": ""
    },
    8: {
        "action": "Finalize EVM Contract",
        "fields": ["token", "encodedFinalizeEvmContractVariant", "createNonce"],
        "notes": "Variant: 1=Create, 2=FirstStorageSlot, 3=CustomStorageSlot. createNonce used only for Create."
    },
    9: {
        "action": "Add API wallet",
        "fields": ["apiWalletAddress", "apiWalletName"],
        "notes": "If apiWalletName is empty, this becomes the main API wallet."
    },
    10: {
        "action": "Cancel order by oid",
        "fields": ["asset", "oid"],
        "notes": ""
    },
    11: {
        "action": "Cancel order by cloid",
        "fields": ["asset", "cloid"],
        "notes": ""
    },
    12: {
        "action": "Approve builder fee",
        "fields": ["maxFeeRate", "builderAddress"],
        "notes": "maxFeeRate is decibps. Example: 10 = 0.01%."
    },
    13: {
        "action": "Send asset (testnet only)",
        "fields": ["destination", "subAccount", "source_dex", "destination_dex", "token", "wei"],
        "notes": "If subAccount != 0x0, transfer from subAccount. Use uint32::MAX for spot dex."
    },
    14: {
        "action": "Reflect EVM supply change (testnet only)",
        "fields": ["token", "wei", "is_mint"],
        "notes": "Used only for aligned quote token contracts."
    }
}

# Action names mapping
ACTION_NAMES = {
    1: "LimitOrder",
    2: "VaultTransfer",
    3: "TokenDelegate",
    4: "StakingDeposit",
    5: "StakingWithdraw",
    6: "SpotSend",
    7: "USDClassTransfer",
    8: "FinalizeEvmContract",
    9: "AddApiWallet",
    10: "CancelOrderByOid",
    11: "CancelOrderByCloid",
    12: "ApproveBuilderFee",
    13: "SendAsset",  # testnet only
    14: "ReflectEvmSupplyChange"  # testnet only
}

