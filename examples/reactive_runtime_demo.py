"""Computed state and batched transaction demo for SwirUI."""

from swirui import State, computed, state_transaction


price = State(12.0)
quantity = State(2)
discount = State(0.0)

subtotal = computed(lambda: price.value * quantity.value)
total = computed(lambda: subtotal.value * (1.0 - discount.value))

total.subscribe(lambda value: print(f"Total: {value:.2f}"), immediate=True)

with state_transaction():
    price.set(15.0)
    quantity.set(3)
    discount.set(0.10)

print(f"Subtotal: {subtotal.value:.2f}")
print(f"Final total: {total.value:.2f}")
