import logging
import time
from utils.blockchain_connector import BlockchainConnector

class AerodromeStakingManager:
    """
    A class to manage Aerodrome Finance staking operations.
    
    This class handles:
    - Staking LP tokens into Aerodrome gauges
    - Unstaking LP tokens from gauges
    - Claiming AERO rewards
    - Withdrawing from closed pools
    """
    
    def __init__(self, pool_address):
        """
        Initialize the AerodromeStakingManager.
        
        Args:
            pool_address (str): Address of the Aerodrome liquidity pool
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.disabled = True
        
        self.blockchain_connector = BlockchainConnector()
        self.pool_address = pool_address
        
        # Load contracts
        self.voter_address = "0x16613524e02ad97eDfeF371bC883F2F5d6C480A5"
        self.voter_contract = self.blockchain_connector.load_contract(
            self.voter_address, 
            "aerodrome_voter_abi.json"
        )
        
        # Get gauge address for this pool
        self.gauge_address = self.voter_contract.functions.gauges(pool_address).call()
        if self.gauge_address == "0x0000000000000000000000000000000000000000":
            raise ValueError(f"No gauge found for pool {pool_address}")
            
        self.gauge_contract = self.blockchain_connector.load_contract(
            self.gauge_address,
            "aerodrome_gauge_abi.json"
        )
        
        self.pool_contract = self.blockchain_connector.load_contract(
            pool_address,
            "aerodrome_pool_abi.json"
        )
        
        # Get AERO token address
        self.aero_address = self.blockchain_connector.token_addresses["AERO"]
        
        self.logger.info(f"Initialized AerodromeStakingManager for pool: {pool_address}")
        self.logger.info(f"Associated gauge: {self.gauge_address}")
    
    def stake_lp_tokens(self, amount):
        """
        Stakes LP tokens into the Aerodrome gauge.
        
        Args:
            amount (float): Amount of LP tokens to stake
            
        Returns:
            str: Transaction hash of the staking transaction
        """
        try:
            # Convert to blockchain units (LP tokens typically have 18 decimals)
            amount_units = self.blockchain_connector.to_blockchain_unit(amount, 18)
            
            # Approve gauge to spend LP tokens
            self.blockchain_connector.approve_token(
                self.pool_address,
                self.gauge_address,
                amount_units
            )
            
            # Stake the LP tokens
            deposit_function = self.gauge_contract.functions.deposit(amount_units)
            tx_hash, receipt = self.blockchain_connector.build_and_send_transaction(deposit_function)
            
            self.logger.info(f"Successfully staked {amount} LP tokens. Transaction hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            self.logger.error(f"Failed to stake LP tokens: {e}")
            raise RuntimeError("Failed to stake LP tokens") from e
    
    def unstake_lp_tokens(self, amount):
        """
        Unstakes LP tokens from the Aerodrome gauge.
        
        Args:
            amount (float): Amount of LP tokens to unstake
            
        Returns:
            str: Transaction hash of the unstaking transaction
        """
        try:
            # Convert to blockchain units
            amount_units = self.blockchain_connector.to_blockchain_unit(amount, 18)
            
            # Withdraw the LP tokens
            withdraw_function = self.gauge_contract.functions.withdraw(amount_units)
            tx_hash, receipt = self.blockchain_connector.build_and_send_transaction(withdraw_function)
            
            self.logger.info(f"Successfully unstaked {amount} LP tokens. Transaction hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            self.logger.error(f"Failed to unstake LP tokens: {e}")
            raise RuntimeError("Failed to unstake LP tokens") from e
    
    def claim_aero_rewards(self):
        """
        Claims AERO token rewards from the gauge.
        
        Returns:
            str: Transaction hash of the claim transaction
        """
        try:
            # Get pending rewards before claiming
            pending_rewards = self.get_pending_rewards()
            
            # Claim rewards
            claim_function = self.gauge_contract.functions.getReward()
            tx_hash, receipt = self.blockchain_connector.build_and_send_transaction(claim_function)
            
            self.logger.info(f"Successfully claimed {pending_rewards} AERO rewards. Transaction hash: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            self.logger.error(f"Failed to claim AERO rewards: {e}")
            raise RuntimeError("Failed to claim AERO rewards") from e
    
    def withdraw_from_closed_pool(self):
        """
        Withdraws all staked LP tokens and claims all pending rewards.
        This is typically used when a pool is closed or you want to exit completely.
        
        Returns:
            dict: Dictionary containing transaction hashes for unstaking and claiming
        """
        try:
            # Get current staked balance
            staked_balance = self.get_staked_balance()
            
            if staked_balance == 0:
                self.logger.info("No LP tokens staked to withdraw")
                return {"unstake_tx": None, "claim_tx": None}
            
            # Unstake all LP tokens
            unstake_tx = self.unstake_lp_tokens(staked_balance)
            
            # Claim all pending rewards
            claim_tx = self.claim_aero_rewards()
            
            result = {
                "unstake_tx": unstake_tx,
                "claim_tx": claim_tx,
                "withdrawn_amount": staked_balance
            }
            
            self.logger.info(f"Successfully withdrew from closed pool. Unstaked: {staked_balance} LP tokens")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to withdraw from closed pool: {e}")
            raise RuntimeError("Failed to withdraw from closed pool") from e
    
    def get_staked_balance(self):
        """
        Gets the current staked LP token balance.
        
        Returns:
            float: Current staked balance in human-readable format
        """
        try:
            balance_units = self.gauge_contract.functions.balanceOf(
                self.blockchain_connector.public_address
            ).call()
            
            balance = self.blockchain_connector.to_human_readable(balance_units, 18)
            return balance
            
        except Exception as e:
            self.logger.error(f"Failed to get staked balance: {e}")
            return 0
    
    def get_pending_rewards(self):
        """
        Gets the pending AERO rewards.
        
        Returns:
            float: Pending rewards in human-readable format
        """
        try:
            rewards_units = self.gauge_contract.functions.earned(
                self.blockchain_connector.public_address
            ).call()
            
            rewards = self.blockchain_connector.to_human_readable(rewards_units, 18)
            return rewards
            
        except Exception as e:
            self.logger.error(f"Failed to get pending rewards: {e}")
            return 0
    
    def get_lp_token_balance(self):
        """
        Gets the LP token balance in the wallet (not staked).
        
        Returns:
            float: LP token balance in human-readable format
        """
        try:
            return self.blockchain_connector.get_token_balance(self.pool_address)
        except Exception as e:
            self.logger.error(f"Failed to get LP token balance: {e}")
            return 0
    
    def get_aero_balance(self):
        """
        Gets the AERO token balance in the wallet.
        
        Returns:
            float: AERO token balance in human-readable format
        """
        try:
            return self.blockchain_connector.get_token_balance(self.aero_address)
        except Exception as e:
            self.logger.error(f"Failed to get AERO balance: {e}")
            return 0
    
    def get_staking_info(self):
        """
        Gets comprehensive staking information.
        
        Returns:
            dict: Dictionary containing all relevant staking information
        """
        try:
            info = {
                "pool_address": self.pool_address,
                "gauge_address": self.gauge_address,
                "lp_balance": self.get_lp_token_balance(),
                "staked_balance": self.get_staked_balance(),
                "pending_rewards": self.get_pending_rewards(),
                "aero_balance": self.get_aero_balance()
            }
            
            self.logger.info(f"Staking info retrieved: {info}")
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get staking info: {e}")
            raise RuntimeError("Failed to get staking info") from e