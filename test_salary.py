from salary import offer_salary

assert offer_salary("Compensation: $60,000 - $72,000 per year") == 72000
assert offer_salary("Salary range 90K-120K USD") == 120000
assert offer_salary("We pay $4,500 per month") == 54000
assert offer_salary("Rate: $40/hr") == 83200
assert offer_salary("€50.000 - €65.000") == 65000
assert offer_salary("No salary info, 401k and 5 years experience") is None
assert offer_salary(None) is None
print("ok")
