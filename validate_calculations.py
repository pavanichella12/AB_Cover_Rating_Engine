"""
Validation Script for Rating Engine Calculations
Tests if calculations match expected logic
"""

import pandas as pd
import sys
from agents.rating_engine_agent_llm import RatingEngineAgentLLM

def create_test_data():
    """
    Create simple test data to validate calculations.
    
    Test Scenario:
    - Deductible = 20 days
    - CC Days = 60 days
    - CC Maximum = 80 days
    - Replacement Cost = $150/day
    
    Teachers:
    - Teacher A: 15 days (below deductible) → Should NOT be in CC range
    - Teacher B: 50 days (in CC range: 21-80) → Should count 30 days (50-20)
    - Teacher C: 75 days (in CC range: 21-80) → Should count 55 days (75-20)
    - Teacher D: 100 days (high claimant >80) → Should count 20 excess days (100-80)
    """
    
    # Create test data
    test_data = {
        'School Year': ['2020-2021', '2020-2021', '2020-2021', '2020-2021'],
        'Employee Identifier': ['Teacher_A', 'Teacher_B', 'Teacher_C', 'Teacher_D'],
        'Total_Days': [15, 50, 75, 100]
    }
    
    return pd.DataFrame(test_data)

def validate_calculations():
    """Validate Rating Engine calculations with test data."""
    
    print("=" * 80)
    print("RATING ENGINE VALIDATION TEST")
    print("=" * 80)
    print()
    
    # Test parameters
    deductible = 20
    cc_days = 60
    cc_maximum = deductible + cc_days  # 80
    replacement_cost = 150.0
    ark_commission_rate = 0.15
    abcover_commission_rate = 0.15
    
    print(f"Test Parameters:")
    print(f"  Deductible: {deductible} days")
    print(f"  CC Days: {cc_days} days")
    print(f"  CC Maximum: {cc_maximum} days")
    print(f"  Replacement Cost: ${replacement_cost}/day")
    print(f"  ARK Commission: {ark_commission_rate*100}%")
    print(f"  ABCover Commission: {abcover_commission_rate*100}%")
    print()
    
    # Create test data
    teacher_days = create_test_data()
    
    print("Test Data (Teacher Absence Days):")
    print(teacher_days.to_string(index=False))
    print()
    
    # Expected results
    print("=" * 80)
    print("EXPECTED RESULTS (Manual Calculation):")
    print("=" * 80)
    print()
    
    # Teacher A: 15 days (below deductible) → NOT in CC range
    print("Teacher A: 15 days")
    print("  → Below Deductible (≤20) → NOT in CC Range")
    print()
    
    # Teacher B: 50 days (in CC range)
    print("Teacher B: 50 days")
    print("  → In CC Range (21-80)")
    print("  → CC Days to count: 50 - 20 = 30 days")
    print()
    
    # Teacher C: 75 days (in CC range)
    print("Teacher C: 75 days")
    print("  → In CC Range (21-80)")
    print("  → CC Days to count: 75 - 20 = 55 days")
    print()
    
    # Teacher D: 100 days (high claimant)
    print("Teacher D: 100 days")
    print("  → High Claimant (>80)")
    print("  → Excess Days: 100 - 80 = 20 days")
    print()
    
    # Expected totals
    expected_staff_cc_range = 2  # Teacher B and C
    expected_total_cc_days = 30 + 55  # 85 days
    expected_replacement_cost_cc = 85 * 150  # $12,750
    expected_high_claimant_staff = 1  # Teacher D
    expected_excess_days = 20  # Teacher D
    expected_high_claimant_cost = 20 * 150  # $3,000
    expected_ark_commission = 12750 * 0.15  # $1,912.50
    expected_abcover_commission = 12750 * 0.15  # $1,912.50
    expected_total_premium = 12750 + 1912.50 + 1912.50  # $16,575
    
    print("Expected Totals:")
    print(f"  Staff in CC Range: {expected_staff_cc_range}")
    print(f"  Total CC Days: {expected_total_cc_days}")
    print(f"  Replacement Cost × CC Days: ${expected_replacement_cost_cc:,.2f}")
    print(f"  High Claimant Staff: {expected_high_claimant_staff}")
    print(f"  Excess Days: {expected_excess_days}")
    print(f"  High Claimant Cost: ${expected_high_claimant_cost:,.2f}")
    print(f"  ARK Commission: ${expected_ark_commission:,.2f}")
    print(f"  ABCover Commission: ${expected_abcover_commission:,.2f}")
    print(f"  Total Premium: ${expected_total_premium:,.2f}")
    print()
    
    # Run actual calculations
    print("=" * 80)
    print("ACTUAL RESULTS (From Rating Engine):")
    print("=" * 80)
    print()
    
    try:
        # Create cleaned_data DataFrame (for per-school-year metrics)
        cleaned_data = pd.DataFrame({
            'School Year': ['2020-2021'] * 4,
            'Employee Identifier': ['Teacher_A', 'Teacher_B', 'Teacher_C', 'Teacher_D'],
            'Absence_Days': [15, 50, 75, 100]
        })
        
        # Initialize agent
        agent = RatingEngineAgentLLM()
        
        # Calculate
        results, reasoning = agent.process(
            teacher_days,
            cleaned_data,
            deductible,
            cc_days,
            replacement_cost,
            ark_commission_rate,
            abcover_commission_rate,
            school_name="Test School",
            blackboard_context=None,
            school_year_days=180
        )
        
        # Display results
        print(f"Staff in CC Range: {results['num_staff_cc_range']}")
        print(f"Total CC Days: {results['total_cc_days']}")
        print(f"Replacement Cost × CC Days: ${results['replacement_cost_cc']:,.2f}")
        print(f"High Claimant Staff: {results['num_high_claimant']}")
        print(f"Excess Days: {results['excess_days']}")
        print(f"High Claimant Cost: ${results['high_claimant_cost']:,.2f}")
        print(f"ARK Commission: ${results['ark_commission']:,.2f}")
        print(f"ABCover Commission: ${results['abcover_commission']:,.2f}")
        print(f"Total Premium: ${results['total_premium']:,.2f}")
        print()
        
        # Validation
        print("=" * 80)
        print("VALIDATION:")
        print("=" * 80)
        print()
        
        checks = [
            ("Staff in CC Range", results['num_staff_cc_range'], expected_staff_cc_range),
            ("Total CC Days", results['total_cc_days'], expected_total_cc_days),
            ("Replacement Cost × CC Days", results['replacement_cost_cc'], expected_replacement_cost_cc),
            ("High Claimant Staff", results['num_high_claimant'], expected_high_claimant_staff),
            ("Excess Days", results['excess_days'], expected_excess_days),
            ("High Claimant Cost", results['high_claimant_cost'], expected_high_claimant_cost),
            ("ARK Commission", results['ark_commission'], expected_ark_commission),
            ("ABCover Commission", results['abcover_commission'], expected_abcover_commission),
            ("Total Premium", results['total_premium'], expected_total_premium),
        ]
        
        all_passed = True
        for metric, actual, expected in checks:
            if abs(actual - expected) < 0.01:  # Allow small floating point differences
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                all_passed = False
            print(f"{status} - {metric}: Actual={actual}, Expected={expected}")
        
        print()
        if all_passed:
            print("🎉 ALL VALIDATIONS PASSED!")
        else:
            print("⚠️  SOME VALIDATIONS FAILED - Please check calculations")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = validate_calculations()
    sys.exit(0 if success else 1)
