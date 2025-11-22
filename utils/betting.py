"""
TakeFreePoints.com - Betting Utilities
Kelly Criterion, odds conversion, and bet sizing functions
"""
import math
from typing import Optional


def american_to_decimal(american_odds: int) -> float:
    """
    Convert American odds to decimal odds

    Examples:
        -110 -> 1.909
        +150 -> 2.50
    """
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """
    Convert decimal odds to implied probability

    Example:
        1.909 -> 0.524 (52.4%)
    """
    return 1 / decimal_odds


def american_to_implied_probability(american_odds: int) -> float:
    """
    Convert American odds directly to implied probability

    Examples:
        -110 -> 0.524 (52.4%)
        +150 -> 0.40 (40%)
    """
    decimal = american_to_decimal(american_odds)
    return decimal_to_implied_probability(decimal)


def kelly_criterion(
    win_probability: float,
    decimal_odds: float,
    fraction: float = 1.0
) -> float:
    """
    Calculate Kelly Criterion bet size as fraction of bankroll

    Formula: f* = (bp - q) / b
    Where:
        f* = fraction of bankroll to bet
        b = decimal odds - 1 (net odds)
        p = probability of winning (our edge)
        q = probability of losing (1 - p)

    Args:
        win_probability: Our estimated probability of winning (0-1)
        decimal_odds: The decimal odds we're getting
        fraction: Kelly fraction to use (e.g., 0.25 for quarter Kelly)

    Returns:
        Fraction of bankroll to bet (0-1)
        Returns 0 if no edge or negative edge
    """
    if win_probability <= 0 or win_probability >= 1:
        return 0.0

    if decimal_odds <= 1:
        return 0.0

    # Calculate net odds (b)
    b = decimal_odds - 1

    # Probability of losing
    q = 1 - win_probability

    # Kelly formula
    kelly_fraction = (b * win_probability - q) / b

    # No edge? No bet
    if kelly_fraction <= 0:
        return 0.0

    # Apply fractional Kelly (for risk management)
    return kelly_fraction * fraction


def calculate_bet_size(
    bankroll: float,
    strategy_type: str,
    win_probability: Optional[float] = None,
    american_odds: Optional[int] = None,
    kelly_fraction: float = 0.25,
    flat_amount: Optional[float] = None,
    percentage: Optional[float] = None,
    max_bet: Optional[float] = None
) -> float:
    """
    Calculate bet size based on strategy type

    Args:
        bankroll: Current bankroll ($)
        strategy_type: "kelly", "flat", or "percentage"
        win_probability: For Kelly - estimated win probability (0-1)
        american_odds: For Kelly - the odds we're getting
        kelly_fraction: For Kelly - fraction to use (default 0.25)
        flat_amount: For flat betting - fixed $ amount
        percentage: For percentage - fraction of bankroll (e.g., 0.02 = 2%)
        max_bet: Hard cap on bet size ($)

    Returns:
        Bet size in dollars
    """
    if strategy_type == "kelly":
        if win_probability is None or american_odds is None:
            raise ValueError("Kelly strategy requires win_probability and american_odds")

        decimal_odds = american_to_decimal(american_odds)
        kelly_frac = kelly_criterion(win_probability, decimal_odds, kelly_fraction)
        bet_size = bankroll * kelly_frac

    elif strategy_type == "flat":
        if flat_amount is None:
            raise ValueError("Flat strategy requires flat_amount")
        bet_size = flat_amount

    elif strategy_type == "percentage":
        if percentage is None:
            raise ValueError("Percentage strategy requires percentage")
        bet_size = bankroll * percentage

    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    # Apply max bet cap if specified
    if max_bet is not None:
        bet_size = min(bet_size, max_bet)

    # Never bet more than bankroll
    bet_size = min(bet_size, bankroll)

    # Round to 2 decimal places (cents)
    return round(bet_size, 2)


def calculate_to_win(stake: float, american_odds: int) -> float:
    """
    Calculate potential profit from a bet

    Args:
        stake: Amount wagered ($)
        american_odds: American odds (e.g., -110, +150)

    Returns:
        Potential profit ($) - not including original stake
    """
    if american_odds > 0:
        # Underdog
        return stake * (american_odds / 100)
    else:
        # Favorite
        return stake * (100 / abs(american_odds))


def calculate_profit_loss(
    stake: float,
    american_odds: int,
    won: bool
) -> float:
    """
    Calculate actual P&L for a settled bet

    Args:
        stake: Amount wagered ($)
        american_odds: American odds
        won: True if bet won, False if lost

    Returns:
        Profit/loss ($) - positive for wins, negative for losses
    """
    if won:
        return calculate_to_win(stake, american_odds)
    else:
        return -stake


def estimate_win_probability_from_edge(
    predicted_value: float,
    line_value: float,
    pick: str,
    historical_std_dev: float = 5.0
) -> float:
    """
    Estimate win probability based on our edge

    This is a simplified model. For real betting, you'd want a more
    sophisticated approach based on historical model performance.

    Args:
        predicted_value: Our model's prediction
        line_value: The betting line
        pick: "over" or "under"
        historical_std_dev: Historical standard deviation of predictions

    Returns:
        Estimated win probability (0-1)
    """
    edge = predicted_value - line_value

    # If pick is "under", flip the edge
    if pick.lower() == "under":
        edge = -edge

    # Edge should be positive for our pick direction
    if edge <= 0:
        return 0.5  # No edge = coin flip

    # Use normal distribution to estimate probability
    # Assuming prediction error follows normal distribution
    from math import erf, sqrt

    # Z-score: how many standard deviations away
    z = edge / historical_std_dev

    # Cumulative probability using error function
    prob = 0.5 * (1 + erf(z / sqrt(2)))

    # Cap at reasonable bounds (never 100% certain)
    return min(max(prob, 0.51), 0.75)


# Example usage and testing
if __name__ == "__main__":
    print("🎲 TakeFreePoints Betting Utilities")
    print("=" * 50)

    # Example 1: Kelly Criterion
    print("\nExample 1: Kelly Criterion")
    bankroll = 100.0
    win_prob = 0.58  # 58% win probability (8% edge over 50%)
    odds = -110

    decimal_odds = american_to_decimal(odds)
    kelly_frac = kelly_criterion(win_prob, decimal_odds, fraction=0.25)
    bet_size = bankroll * kelly_frac

    print(f"Bankroll: ${bankroll}")
    print(f"Win probability: {win_prob * 100}%")
    print(f"Odds: {odds} (decimal: {decimal_odds:.3f})")
    print(f"Quarter Kelly fraction: {kelly_frac * 100:.2f}%")
    print(f"Bet size: ${bet_size:.2f}")

    # Example 2: Calculate bet size with helper
    print("\n\nExample 2: Calculate Bet Size")
    bet = calculate_bet_size(
        bankroll=100.0,
        strategy_type="kelly",
        win_probability=0.58,
        american_odds=-110,
        kelly_fraction=0.25,
        max_bet=20.0
    )
    to_win = calculate_to_win(bet, -110)
    print(f"Bet: ${bet:.2f}")
    print(f"To win: ${to_win:.2f}")

    # Example 3: Estimate win probability from model edge
    print("\n\nExample 3: Win Probability from Edge")
    predicted = 27.5
    line = 25.5
    pick = "over"
    edge = predicted - line

    win_prob_est = estimate_win_probability_from_edge(predicted, line, pick)
    print(f"Predicted: {predicted} points")
    print(f"Line: {line} points")
    print(f"Edge: +{edge} points")
    print(f"Estimated win probability: {win_prob_est * 100:.1f}%")

    print("\n" + "=" * 50)
