"""Tests for Brownian bridge barrier monitoring."""

import pytest
import numpy as np

from pricer.engines.path_generator import brownian_bridge_hit_probability


class TestBrownianBridgeHitProbability:
    """Tests for Brownian bridge barrier probability calculation."""
    
    def test_endpoints_at_barrier(self) -> None:
        """If endpoint is at or below barrier, probability is 1."""
        S_start = np.array([100.0])
        S_end = np.array([60.0])  # At barrier
        barrier = np.array([60.0])
        vol = np.array([0.25])
        dt = 0.5
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt, down=True)
        assert prob[0] == 1.0
    
    def test_start_at_barrier(self) -> None:
        """If start is at barrier, probability is 1."""
        S_start = np.array([60.0])
        S_end = np.array([100.0])
        barrier = np.array([60.0])
        vol = np.array([0.25])
        dt = 0.5
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt, down=True)
        assert prob[0] == 1.0
    
    def test_far_from_barrier_low_prob(self) -> None:
        """If both endpoints far from barrier, probability is low."""
        S_start = np.array([100.0])
        S_end = np.array([110.0])
        barrier = np.array([60.0])
        vol = np.array([0.20])
        dt = 0.25  # 3 months
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt, down=True)
        
        # Should be very low probability
        assert prob[0] < 0.10
    
    def test_probability_increases_with_volatility(self) -> None:
        """Higher vol should increase hit probability."""
        S_start = np.array([100.0])
        S_end = np.array([95.0])
        barrier = np.array([70.0])
        dt = 0.5
        
        prob_low_vol = brownian_bridge_hit_probability(
            S_start, S_end, barrier, np.array([0.15]), dt
        )
        prob_high_vol = brownian_bridge_hit_probability(
            S_start, S_end, barrier, np.array([0.40]), dt
        )
        
        assert prob_high_vol[0] > prob_low_vol[0]
    
    def test_probability_increases_closer_to_barrier(self) -> None:
        """Closer to barrier should increase hit probability."""
        S_start = np.array([100.0, 100.0])
        S_end = np.array([90.0, 75.0])  # Second is closer to barrier
        barrier = np.array([70.0, 70.0])
        vol = np.array([0.25, 0.25])
        dt = 0.5
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt)
        
        # Second path (closer to barrier) should have higher prob
        assert prob[1] > prob[0]
    
    def test_probability_decreases_with_shorter_time(self) -> None:
        """Less time should decrease hit probability."""
        S_start = np.array([100.0])
        S_end = np.array([90.0])
        barrier = np.array([70.0])
        vol = np.array([0.25])
        
        prob_long = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, 1.0)
        prob_short = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, 0.1)
        
        assert prob_long[0] > prob_short[0]
    
    def test_zero_dt_returns_zero(self) -> None:
        """Zero time step should return zero (or at most endpoint check)."""
        S_start = np.array([100.0])
        S_end = np.array([100.0])
        barrier = np.array([70.0])
        vol = np.array([0.25])
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, 0.0)
        assert prob[0] == 0.0
    
    def test_vectorized_computation(self) -> None:
        """Test vectorized computation with multiple paths."""
        rng = np.random.default_rng(42)
        n_paths = 1000
        
        S_start = rng.uniform(90, 110, n_paths)
        S_end = rng.uniform(85, 115, n_paths)
        barrier = np.full(n_paths, 70.0)
        vol = np.full(n_paths, 0.25)
        dt = 0.5
        
        prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt)
        
        # Should return array of correct shape
        assert prob.shape == (n_paths,)
        
        # All probabilities should be in [0, 1]
        assert np.all(prob >= 0)
        assert np.all(prob <= 1)
    
    def test_monotonicity_closer_barrier_higher_prob(self) -> None:
        """
        Closer barrier should ALWAYS result in higher hitting probability.
        
        This is a critical monotonicity property for the Brownian bridge formula.
        """
        S_start = np.array([100.0])
        S_end = np.array([95.0])
        vol = np.array([0.25])
        dt = 0.5
        
        # Test a range of barrier distances
        barriers = [90.0, 85.0, 80.0, 75.0, 70.0, 65.0]
        probs = []
        
        for barrier_level in barriers:
            barrier = np.array([barrier_level])
            prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt)
            probs.append(prob[0])
        
        # Closer barrier (higher value) should give higher probability
        for i in range(len(probs) - 1):
            assert probs[i] >= probs[i + 1], \
                f"Barrier {barriers[i]} prob {probs[i]} should be >= barrier {barriers[i+1]} prob {probs[i+1]}"
    
    def test_monotonicity_lower_vol_lower_prob(self) -> None:
        """
        Lower volatility should result in lower hitting probability.
        
        Less vol = more predictable paths = less likely to deviate to barrier.
        """
        S_start = np.array([100.0])
        S_end = np.array([95.0])
        barrier = np.array([70.0])
        dt = 0.5
        
        # Test a range of volatilities
        vols = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
        probs = []
        
        for vol_level in vols:
            vol = np.array([vol_level])
            prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt)
            probs.append(prob[0])
        
        # Higher vol should give higher probability
        for i in range(len(probs) - 1):
            assert probs[i] <= probs[i + 1], \
                f"Vol {vols[i]} prob {probs[i]} should be <= vol {vols[i+1]} prob {probs[i+1]}"
    
    def test_monotonicity_longer_time_higher_prob(self) -> None:
        """
        Longer time interval should give higher hitting probability.
        
        More time = more opportunity to hit the barrier.
        """
        S_start = np.array([100.0])
        S_end = np.array([95.0])
        barrier = np.array([70.0])
        vol = np.array([0.25])
        
        # Test a range of time intervals
        dts = [0.1, 0.25, 0.5, 1.0, 2.0]
        probs = []
        
        for dt in dts:
            prob = brownian_bridge_hit_probability(S_start, S_end, barrier, vol, dt)
            probs.append(prob[0])
        
        # Longer time should give higher probability
        for i in range(len(probs) - 1):
            assert probs[i] <= probs[i + 1], \
                f"dt {dts[i]} prob {probs[i]} should be <= dt {dts[i+1]} prob {probs[i+1]}"
