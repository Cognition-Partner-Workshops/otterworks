"
Online quote rating. Rates use 4 implied decimals, factors 3 and
modifiers 2; each step rounds half up to the cent.
"
Class {
	#name : 'InsQuoteEngine',
	#superclass : 'Object',
	#instVars : [ 'tables' ],
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'instance creation' }
InsQuoteEngine class >> on: someTables [
	^ self new setTables: someTables
]

{ #category : 'initialization' }
InsQuoteEngine >> setTables: someTables [ tables := someTables ]

{ #category : 'arithmetic' }
InsQuoteEngine >> round: anInteger scale: aScale [
	"Divide by aScale, rounding half up (amounts here are never negative)."
	^ (anInteger * 2 + aScale) // (aScale * 2)
]

{ #category : 'rating' }
InsQuoteEngine >> quote: aPolicy [
	| q |
	q := InsQuote new policyId: aPolicy id; yourself.
	self validateLine: aPolicy into: q.
	q isOk ifTrue: [ self validateExposure: aPolicy into: q ].
	q isOk ifTrue: [ self checkEligibility: aPolicy into: q ].
	q isOk ifTrue: [ self lookupClassRate: aPolicy into: q ].
	q isOk ifTrue: [ self lookupTerritory: aPolicy into: q ].
	q isOk ifFalse: [ ^ q ].
	self lookupOverride: aPolicy into: q.
	self rate: aPolicy into: q.
	^ q
]

{ #category : 'rating' }
InsQuoteEngine >> rate: aPolicy into: q [
	| premium |
	premium := self basePremium: aPolicy quote: q.
	q basePremium: premium.
	premium := self experienceMod: aPolicy premium: premium.
	premium := self deductibleCredit: aPolicy premium: premium.
	premium := self applyMinimum: aPolicy premium: premium quote: q.
	premium := self scheduleMod: aPolicy premium: premium.
	premium := self multiPolicy: aPolicy premium: premium.
	q modifiedPremium: premium.
	q endorsements: (self endorsements: aPolicy premium: premium).
	q fee: self policyFee.
	q total: premium + q endorsements + q fee
]

{ #category : 'validation' }
InsQuoteEngine >> validateLine: aPolicy into: q [
	(#('GL' 'PR' 'CA') includes: aPolicy line) ifFalse: [ q reject: 'LN' ]
]

{ #category : 'validation' }
InsQuoteEngine >> validateExposure: aPolicy into: q [
	aPolicy exposureCents > 0 ifFalse: [ q reject: 'EX' ]
]

{ #category : 'lookup' }
InsQuoteEngine >> checkEligibility: aPolicy into: q [
	"A row for the policy's state wins over the all-states row."
	| matches row |
	matches := tables eligibilityRows select: [ :r |
		(r at: 1) = aPolicy line and: [ (r at: 2) = aPolicy classCode ] ].
	row := matches detect: [ :r | (r at: 3) = aPolicy state ]
		ifNone: [ matches detect: [ :r | (r at: 3) = '**' ] ifNone: [ nil ] ].
	(row notNil and: [ (row at: 4) = 'N' ]) ifTrue: [ q decline: (row at: 5) ]
]

{ #category : 'lookup' }
InsQuoteEngine >> lookupClassRate: aPolicy into: q [
	| row |
	row := tables classRows
		detect: [ :r | (r at: 1) = aPolicy line and: [ (r at: 2) = aPolicy classCode
			and: [ tables row: r from: 4 inForceOn: aPolicy effective ] ] ]
		ifNone: [ ^ q reject: 'CL' ].
	q baseRate: (self scaled: (row at: 3) places: 4)
]

{ #category : 'lookup' }
InsQuoteEngine >> lookupTerritory: aPolicy into: q [
	"A territory with no row in force falls back to territory 000."
	| row |
	row := tables territoryRows
		detect: [ :r | (r at: 1) = aPolicy line and: [ (r at: 2) = aPolicy territory
			and: [ tables row: r from: 4 inForceOn: aPolicy effective ] ] ]
		ifNone: [ nil ].
	row ifNotNil: [ q factorSource: 'T' ] ifNil: [
		row := tables territoryRows
			detect: [ :r | (r at: 1) = aPolicy line and: [ (r at: 2) = '000'
				and: [ tables row: r from: 4 inForceOn: aPolicy effective ] ] ]
			ifNone: [ ^ q reject: 'TR' ].
		q factorSource: 'D' ].
	q territoryFactor: (self scaled: (row at: 3) places: 3)
]

{ #category : 'lookup' }
InsQuoteEngine >> lookupOverride: aPolicy into: q [
	"An override replaces the territory factor; it never stacks."
	tables overrideRows
		detect: [ :r | (r at: 1) = aPolicy line and: [ (r at: 2) = aPolicy classCode
			and: [ (r at: 3) = aPolicy territory
			and: [ tables row: r from: 5 inForceOn: aPolicy effective ] ] ] ]
		ifFound: [ :r |
			q territoryFactor: (self scaled: (r at: 4) places: 3).
			q factorSource: 'O' ]
		ifNone: [ ]
]

{ #category : 'premium' }
InsQuoteEngine >> basePremium: aPolicy quote: q [
	| step |
	step := self round: aPolicy exposureCents * q baseRate scale: 10000.
	^ self round: step * q territoryFactor scale: 1000
]

{ #category : 'premium' }
InsQuoteEngine >> experienceMod: aPolicy premium: cents [
	| mod |
	mod := aPolicy claims >= 3
		ifTrue: [ 125 ]
		ifFalse: [ (aPolicy claims = 0 and: [ aPolicy yearsInBusiness >= 3 ]) ifTrue: [ 90 ] ifFalse: [ 100 ] ].
	^ self round: cents * mod scale: 100
]

{ #category : 'premium' }
InsQuoteEngine >> deductibleCredit: aPolicy premium: cents [
	"Deductible credits apply to property and auto only."
	| factor d |
	(#('PR' 'CA') includes: aPolicy line) ifFalse: [ ^ cents ].
	d := aPolicy deductible.
	factor := d >= 5000 ifTrue: [ 92 ] ifFalse: [
		d >= 2500 ifTrue: [ 95 ] ifFalse: [ d >= 1000 ifTrue: [ 98 ] ifFalse: [ 100 ] ] ].
	^ self round: cents * factor scale: 100
]

{ #category : 'premium' }
InsQuoteEngine >> applyMinimum: aPolicy premium: cents quote: q [
	"The quote screen floors the premium before schedule and package credits."
	| rows row minimum |
	rows := tables minimumRows select: [ :r | (r at: 1) = aPolicy line ].
	row := rows detect: [ :r | (r at: 2) = aPolicy state ]
		ifNone: [ rows detect: [ :r | (r at: 2) = '**' ] ifNone: [ ^ cents ] ].
	minimum := self scaled: (row at: 3) places: 2.
	cents < minimum ifFalse: [ ^ cents ].
	q minimumApplied: true.
	^ minimum
]

{ #category : 'premium' }
InsQuoteEngine >> scheduleMod: aPolicy premium: cents [
	| mod |
	mod := (aPolicy scheduleMod max: -25) min: 25.
	^ self round: cents * (100 + mod) scale: 100
]

{ #category : 'premium' }
InsQuoteEngine >> multiPolicy: aPolicy premium: cents [
	(aPolicy multiPolicy and: [ #('GL' 'PR') includes: aPolicy line ]) ifFalse: [ ^ cents ].
	^ self round: cents * 95 scale: 100
]

{ #category : 'endorsements' }
InsQuoteEngine >> endorsements: aPolicy premium: cents [
	"Each endorsement is quoted in whole dollars; together they are capped
	 at a quarter of the modified premium."
	| total |
	total := 0.
	aPolicy line = 'GL' ifTrue: [
		total := total + (((aPolicy additionalInsureds max: 0) min: 3) * 5000) ].
	(aPolicy equipment and: [ aPolicy line = 'PR' ]) ifTrue: [
		total := total + (self wholeDollars: ((self round: cents * 3 scale: 100) max: 7500)) ].
	(aPolicy waiver and: [ #('GL' 'CA') includes: aPolicy line ]) ifTrue: [
		total := total + (self wholeDollars: (self round: cents * 2 scale: 100)) ].
	(aPolicy hiredNonOwned and: [ aPolicy line = 'GL' ]) ifTrue: [
		total := total + 12000 ].
	^ total min: (self round: cents * 25 scale: 100)
]

{ #category : 'endorsements' }
InsQuoteEngine >> wholeDollars: cents [
	^ (self round: cents scale: 100) * 100
]

{ #category : 'premium' }
InsQuoteEngine >> policyFee [ ^ 3500 ]

{ #category : 'arithmetic' }
InsQuoteEngine >> scaled: aString places: places [
	"'1.025' with 3 places -> 1025"
	| sign parts whole frac |
	sign := (aString beginsWith: '-') ifTrue: [ -1 ] ifFalse: [ 1 ].
	parts := (aString copyWithout: $-) splitOn: $..
	whole := parts first asInteger ifNil: [ 0 ].
	frac := parts size > 1 ifTrue: [ parts second ] ifFalse: [ '' ].
	frac := (frac , (String new: places withAll: $0)) first: places.
	^ sign * (whole * (10 raisedTo: places) + frac asInteger)
]
