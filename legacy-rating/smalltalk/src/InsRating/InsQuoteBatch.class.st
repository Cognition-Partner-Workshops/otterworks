"
Headless entry point: quote every POLREC record in a file and write one
canonical line per policy.
"
Class {
	#name : 'InsQuoteBatch',
	#superclass : 'Object',
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'running' }
InsQuoteBatch class >> runPolicies: policyPath tables: tableDir out: outPath [
	| engine lines counts |
	engine := InsQuoteEngine on: (InsRatingTables fromDirectory: tableDir).
	counts := Dictionary new.
	lines := (policyPath asFileReference contents lines reject: [ :each | each trimBoth isEmpty ])
		collect: [ :each | | q |
			q := engine quote: (InsPolicy fromRecord: each).
			counts at: q status put: (counts at: q status ifAbsent: [ 0 ]) + 1.
			q asLine ].
	outPath asFileReference ensureDelete; writeStreamDo: [ :s |
		lines do: [ :each | s nextPutAll: each; lf ] ].
	^ 'QUOTE READ=' , lines size printString ,
		' OK=' , (counts at: 'OK' ifAbsent: [ 0 ]) printString ,
		' DEC=' , (counts at: 'DEC' ifAbsent: [ 0 ]) printString ,
		' REJ=' , (counts at: 'REJ' ifAbsent: [ 0 ]) printString
]
