from decimal import Decimal, getcontext, ROUND_HALF_UP

OSAGO_YEARLY = Decimal("2770")
INTEREST_RATE_ANNUAL = Decimal("0.36")
COMMISSION_RATE = Decimal("0.02")

def calculate_leasing(car_price, down_payment, leasing_term_months):
    getcontext().prec = 16

    car_price = Decimal(car_price)
    down_payment = Decimal(down_payment)
    leasing_term = int(leasing_term_months)

    # Только остаток!
    leasing_amount = (car_price - down_payment).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Комиссия — только от остатка!
    commission = (leasing_amount * COMMISSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    osago = OSAGO_YEARLY

    monthly_rate = INTEREST_RATE_ANNUAL / Decimal(12)
    if monthly_rate > 0:
        numerator = monthly_rate * (1 + monthly_rate) ** leasing_term
        denominator = (1 + monthly_rate) ** leasing_term - 1
        monthly_payment = leasing_amount * numerator / denominator
    else:
        monthly_payment = leasing_amount / leasing_term
    monthly_payment = monthly_payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ВСЁ, что отдаст клиент ЗА ВСЁ время (взнос + комиссия + осаго + все месячные платежи)
    car_total_cost = (monthly_payment * leasing_term).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "car_total_cost": car_total_cost,
        "monthly_payment": monthly_payment, 
        "commission": commission,
        "osago": osago,
        "down_payment": down_payment,
    }

