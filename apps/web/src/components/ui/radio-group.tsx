"use client"

import * as React from "react"

const RadioGroup = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { value?: string; onValueChange?: (value: string) => void; defaultValue?: string }
>(({ className = "", value, onValueChange, defaultValue, children, ...props }, ref) => {
  const [internalValue, setInternalValue] = React.useState(defaultValue || "")
  const currentValue = value ?? internalValue

  const handleChange = (newValue: string) => {
    setInternalValue(newValue)
    onValueChange?.(newValue)
  }

  return (
    <div ref={ref} role="radiogroup" className={`grid gap-2 ${className}`} {...props}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, {
            _selected: currentValue,
            _onSelect: handleChange,
          })
        }
        return child
      })}
    </div>
  )
})
RadioGroup.displayName = "RadioGroup"

const RadioGroupItem = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string; _selected?: string; _onSelect?: (v: string) => void }
>(({ className = "", value, _selected, _onSelect, ...props }, ref) => {
  const isSelected = _selected === value
  return (
    <button
      ref={ref}
      type="button"
      role="radio"
      aria-checked={isSelected}
      onClick={() => _onSelect?.(value)}
      className={`aspect-square h-4 w-4 rounded-full border border-zinc-600 ${isSelected ? "border-blue-500 bg-blue-500" : ""} ${className}`}
      {...props}
    >
      {isSelected && (
        <span className="flex items-center justify-center">
          <span className="h-2 w-2 rounded-full bg-white" />
        </span>
      )}
    </button>
  )
})
RadioGroupItem.displayName = "RadioGroupItem"

export { RadioGroup, RadioGroupItem }
