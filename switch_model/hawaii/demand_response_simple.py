import os
from pyomo.environ import *
from switch_model.financials import capital_recovery_factor as crf

def define_arguments(argparser):
    argparser.add_argument('--demand-response-share', dest='demand_response_share',
        type=float, default=0.10, 
        help=("Fraction of hourly load that can be shifted to other times of "
              "day (default=0.10). This provides default values for all "
              "periods. To provide distinct values for each period, use the "
              "input file demand_response_max_share.tab")
        )

def define_components(m):
    
    m.demand_response_max_share = Param(
        m.PERIODS,
        default=m.options.demand_response_share, 
        doc="Maximum share of hourly load that can be rescheduled, ratio")

    m.ShiftDemand = Var(m.LOAD_ZONES, m.TIMEPOINTS, within=Reals, 
        bounds=lambda m, z, t: (
            -1.0 * m.demand_response_max_share[m.tp_period[t]] * m.zone_demand_mw[z, t],
            None
        ),
        doc="Adjustment to demand during each hour (positive = higher demand)"
    )
    # Register with spinning reserves if it is available
    if 'Spinning_Reserve_Up_Provisions' in dir(m):
        m.HIDemandResponseSimpleSpinningReserveUp = Expression(
            m.BALANCING_AREA_TIMEPOINTS, 
            rule=lambda m, b, t:
                sum(m.ShiftDemand[z, t] -  m.ShiftDemand[z, t].lb
                    for z in m.ZONES_IN_BALANCING_AREA[b])
        )
        m.Spinning_Reserve_Up_Provisions.append(
            'HIDemandResponseSimpleSpinningReserveUp')

    # all changes to demand must balance out over the course of the day
    m.Demand_Response_Net_Zero = Constraint(m.LOAD_ZONES, m.TIMESERIES, 
        rule=lambda m, z, ts:
            sum(m.ShiftDemand[z, tp] for tp in m.TPS_IN_TS[ts]) == 0.0
    )

    # add demand response to the zonal energy balance
    m.Zone_Power_Withdrawals.append('ShiftDemand')


def load_inputs(mod, switch_data, inputs_dir):
    """
    This input file is optional. Any period that doesn't have
    demand_response_max_share specified in a row of this file will get a
    default value from the command-line option --demand-response-share.
    
    demand_response_max_share.tab
        PERIOD, demand_response_max_share
    """
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'demand_response_max_share.tab'),
        autoselect=True,
        param=(mod.demand_response_max_share))
