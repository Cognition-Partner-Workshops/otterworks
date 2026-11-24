"
The online quote screen: a single form served by Zinc. The underwriter keys
a policy, the screen shows each rating step and the quoted total.
"
Class {
	#name : 'InsQuoteScreen',
	#superclass : 'Object',
	#instVars : [ 'engine' ],
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'running' }
InsQuoteScreen class >> serveOn: aPort tables: tableDir [
	| screen |
	screen := self new setEngine: (InsQuoteEngine on: (InsRatingTables fromDirectory: tableDir)).
	^ (ZnServer on: aPort)
		bindingAddress: #[0 0 0 0];
		onRequestRespond: [ :request | screen handle: request ];
		start;
		yourself
]

{ #category : 'initialization' }
InsQuoteScreen >> setEngine: anEngine [ engine := anEngine ]

{ #category : 'serving' }
InsQuoteScreen >> handle: aRequest [
	| fields quote |
	aRequest uri firstPathSegment = 'health' ifTrue: [ ^ ZnResponse ok: (ZnEntity text: 'ok') ].
	fields := aRequest uri query ifNil: [ Dictionary new ].
	quote := (fields includesKey: 'line') ifTrue: [ engine quote: (self policyFrom: fields) ].
	^ ZnResponse ok: (ZnEntity html: (self pageFor: fields quote: quote))
]

{ #category : 'serving' }
InsQuoteScreen >> policyFrom: fields [
	| get |
	get := [ :key :default | (fields at: key ifAbsent: [ default ]) trimBoth ].
	^ InsPolicy new
		id: 'SCREEN';
		line: (get value: 'line' value: '') asUppercase;
		state: (get value: 'state' value: '') asUppercase;
		classCode: (get value: 'class' value: '');
		territory: (get value: 'territory' value: '000');
		effective: (get value: 'effective' value: '0') asInteger;
		exposureCents: (InsQuoteEngine new scaled: (get value: 'exposure' value: '0') places: 2);
		yearsInBusiness: (get value: 'years' value: '0') asInteger;
		claims: (get value: 'claims' value: '0') asInteger;
		deductible: (get value: 'deductible' value: '0') asInteger;
		multiPolicy: (fields includesKey: 'multi');
		scheduleMod: (get value: 'schedule' value: '0') asInteger;
		additionalInsureds: (get value: 'addl' value: '0') asInteger;
		equipment: (fields includesKey: 'equipment');
		waiver: (fields includesKey: 'waiver');
		hiredNonOwned: (fields includesKey: 'hnoa');
		yourself
]

{ #category : 'rendering' }
InsQuoteScreen >> money: cents [
	^ '$' , (cents // 100) printString , '.' , ((cents \\ 100) printPaddedWith: $0 to: 2)
]

{ #category : 'rendering' }
InsQuoteScreen >> pageFor: fields quote: aQuote [
	| input |
	input := [ :label :key :default |
		'<label>' , label , ' <input name="' , key , '" value="' ,
			((fields at: key ifAbsent: [ default ]) asString asHTMLString copyReplaceAll: '"' with: '&quot;') , '"></label>' ].
	^ String streamContents: [ :s |
		s nextPutAll: '<!doctype html><html><head><title>Policy quote</title>',
			'<style>body{font-family:monospace;margin:2em}label{display:block;margin:.3em 0}',
			'table{border-collapse:collapse;margin-top:1em}td{border:1px solid #999;padding:.3em .8em}</style>',
			'</head><body><h1>Policy quote</h1><form method="get">'.
		s nextPutAll: (input value: 'Line' value: 'line' value: 'GL');
			nextPutAll: (input value: 'State' value: 'state' value: 'IL');
			nextPutAll: (input value: 'Class' value: 'class' value: '91340');
			nextPutAll: (input value: 'Territory' value: 'territory' value: '001');
			nextPutAll: (input value: 'Effective (YYYYMMDD)' value: 'effective' value: '20260315');
			nextPutAll: (input value: 'Exposure' value: 'exposure' value: '210.00');
			nextPutAll: (input value: 'Years in business' value: 'years' value: '5');
			nextPutAll: (input value: 'Claims (3 years)' value: 'claims' value: '0');
			nextPutAll: (input value: 'Deductible' value: 'deductible' value: '500');
			nextPutAll: (input value: 'Schedule mod (hundredths)' value: 'schedule' value: '0');
			nextPutAll: (input value: 'Additional insureds' value: 'addl' value: '0').
		#('multi' 'equipment' 'waiver' 'hnoa') with: #('Multi-policy' 'Equipment breakdown' 'Waiver of subrogation' 'Hired and non-owned auto') do: [ :key :label |
			s nextPutAll: '<label><input type="checkbox" name="' , key , '"' ,
				((fields includesKey: key) ifTrue: [ ' checked' ] ifFalse: [ '' ]) , '> ' , label , '</label>' ].
		s nextPutAll: '<button type="submit">Quote</button></form>'.
		aQuote ifNotNil: [
			s nextPutAll: '<table id="quote">'.
			{ 'Status' -> (aQuote status , ' ' , aQuote reason).
			  'Factor source' -> aQuote factorSource.
			  'Base premium' -> (self money: aQuote basePremium).
			  'Minimum applied' -> (aQuote minimumApplied ifTrue: [ 'yes' ] ifFalse: [ 'no' ]).
			  'Modified premium' -> (self money: aQuote modifiedPremium).
			  'Endorsements' -> (self money: aQuote endorsements).
			  'Policy fee' -> (self money: aQuote fee).
			  'Total' -> (self money: aQuote total) } do: [ :row |
				s nextPutAll: '<tr><td>' , row key , '</td><td>' , row value asHTMLString , '</td></tr>' ].
			s nextPutAll: '</table>' ].
		s nextPutAll: '</body></html>' ]
]
