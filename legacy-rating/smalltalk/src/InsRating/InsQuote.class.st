"
The result of one quote. Money in integer cents.
"
Class {
	#name : 'InsQuote',
	#superclass : 'Object',
	#instVars : [ 'policyId', 'status', 'reason', 'baseRate', 'territoryFactor', 'factorSource', 'basePremium', 'modifiedPremium', 'minimumApplied', 'endorsements', 'fee', 'total' ],
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'initialization' }
InsQuote >> initialize [
	status := 'OK'. reason := ''. factorSource := ''.
	baseRate := 0. territoryFactor := 0. basePremium := 0. modifiedPremium := 0.
	minimumApplied := false. endorsements := 0. fee := 0. total := 0
]

{ #category : 'testing' }
InsQuote >> isOk [ ^ status = 'OK' ]

{ #category : 'actions' }
InsQuote >> decline: aReason [ status := 'DEC'. reason := aReason ]
{ #category : 'actions' }
InsQuote >> reject: aReason [ status := 'REJ'. reason := aReason ]

{ #category : 'printing' }
InsQuote >> asLine [
	"Canonical pipe-delimited quote line used by the parity driver."
	^ String streamContents: [ :s |
		{ policyId. status. reason. basePremium. modifiedPremium.
		  minimumApplied ifTrue: [ 'Y' ] ifFalse: [ 'N' ].
		  endorsements. fee. total. factorSource }
			do: [ :each | s nextPutAll: each asString ] separatedBy: [ s nextPut: $| ] ]
]

{ #category : 'accessing' }
InsQuote >> baseRate [ ^ baseRate ]
{ #category : 'accessing' }
InsQuote >> baseRate: n [ baseRate := n ]
{ #category : 'accessing' }
InsQuote >> basePremium [ ^ basePremium ]
{ #category : 'accessing' }
InsQuote >> basePremium: n [ basePremium := n ]
{ #category : 'accessing' }
InsQuote >> endorsements [ ^ endorsements ]
{ #category : 'accessing' }
InsQuote >> endorsements: n [ endorsements := n ]
{ #category : 'accessing' }
InsQuote >> factorSource [ ^ factorSource ]
{ #category : 'accessing' }
InsQuote >> factorSource: s [ factorSource := s ]
{ #category : 'accessing' }
InsQuote >> fee [ ^ fee ]
{ #category : 'accessing' }
InsQuote >> fee: n [ fee := n ]
{ #category : 'accessing' }
InsQuote >> minimumApplied [ ^ minimumApplied ]
{ #category : 'accessing' }
InsQuote >> minimumApplied: b [ minimumApplied := b ]
{ #category : 'accessing' }
InsQuote >> modifiedPremium [ ^ modifiedPremium ]
{ #category : 'accessing' }
InsQuote >> modifiedPremium: n [ modifiedPremium := n ]
{ #category : 'accessing' }
InsQuote >> policyId [ ^ policyId ]
{ #category : 'accessing' }
InsQuote >> policyId: s [ policyId := s ]
{ #category : 'accessing' }
InsQuote >> reason [ ^ reason ]
{ #category : 'accessing' }
InsQuote >> status [ ^ status ]
{ #category : 'accessing' }
InsQuote >> territoryFactor [ ^ territoryFactor ]
{ #category : 'accessing' }
InsQuote >> territoryFactor: n [ territoryFactor := n ]
{ #category : 'accessing' }
InsQuote >> total [ ^ total ]
{ #category : 'accessing' }
InsQuote >> total: n [ total := n ]
