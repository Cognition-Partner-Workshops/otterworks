"
A policy submitted for a quote, read from a POLREC fixed-width record.
Money is held in integer cents; the schedule modifier in hundredths.
"
Class {
	#name : 'InsPolicy',
	#superclass : 'Object',
	#instVars : [ 'id', 'line', 'state', 'classCode', 'territory', 'effective', 'exposureCents', 'yearsInBusiness', 'claims', 'deductible', 'multiPolicy', 'scheduleMod', 'additionalInsureds', 'equipment', 'waiver', 'hiredNonOwned' ],
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'parsing' }
InsPolicy class >> fromRecord: aString [
	| r |
	r := aString , (String new: (80 - aString size max: 0) withAll: $ ).
	^ self new
		id: (r copyFrom: 1 to: 8) trimBoth;
		line: (r copyFrom: 9 to: 10);
		state: (r copyFrom: 11 to: 12);
		classCode: (r copyFrom: 13 to: 17) trimBoth;
		territory: (r copyFrom: 18 to: 20);
		effective: (r copyFrom: 21 to: 28) asInteger;
		exposureCents: (self overpunch: (r copyFrom: 29 to: 37));
		yearsInBusiness: (r copyFrom: 38 to: 39) asInteger;
		claims: (r copyFrom: 40 to: 41) asInteger;
		deductible: (r copyFrom: 42 to: 46) asInteger;
		multiPolicy: (r at: 47) = $Y;
		scheduleMod: (self overpunch: (r copyFrom: 48 to: 50));
		additionalInsureds: (r copyFrom: 51 to: 52) asInteger;
		equipment: (r at: 53) = $Y;
		waiver: (r at: 54) = $Y;
		hiredNonOwned: (r at: 55) = $Y;
		yourself
]

{ #category : 'parsing' }
InsPolicy class >> overpunch: aString [
	"Zoned decimal: the last character carries both the final digit and the sign."
	| last digit negative |
	last := aString last.
	(last between: $0 and: $9)
		ifTrue: [ digit := last digitValue. negative := false ]
		ifFalse: [
			('{ABCDEFGHI' includes: last)
				ifTrue: [ digit := '{ABCDEFGHI' indexOf: last. negative := false ]
				ifFalse: [ digit := '}JKLMNOPQR' indexOf: last. negative := true ].
			digit := digit - 1 ].
	^ ((aString allButLast , digit printString) asInteger) * (negative ifTrue: [ -1 ] ifFalse: [ 1 ])
]

{ #category : 'accessing' }
InsPolicy >> additionalInsureds [ ^ additionalInsureds ]
{ #category : 'accessing' }
InsPolicy >> additionalInsureds: n [ additionalInsureds := n ]
{ #category : 'accessing' }
InsPolicy >> claims [ ^ claims ]
{ #category : 'accessing' }
InsPolicy >> claims: n [ claims := n ]
{ #category : 'accessing' }
InsPolicy >> classCode [ ^ classCode ]
{ #category : 'accessing' }
InsPolicy >> classCode: s [ classCode := s ]
{ #category : 'accessing' }
InsPolicy >> deductible [ ^ deductible ]
{ #category : 'accessing' }
InsPolicy >> deductible: n [ deductible := n ]
{ #category : 'accessing' }
InsPolicy >> effective [ ^ effective ]
{ #category : 'accessing' }
InsPolicy >> effective: n [ effective := n ]
{ #category : 'accessing' }
InsPolicy >> equipment [ ^ equipment ]
{ #category : 'accessing' }
InsPolicy >> equipment: b [ equipment := b ]
{ #category : 'accessing' }
InsPolicy >> exposureCents [ ^ exposureCents ]
{ #category : 'accessing' }
InsPolicy >> exposureCents: n [ exposureCents := n ]
{ #category : 'accessing' }
InsPolicy >> hiredNonOwned [ ^ hiredNonOwned ]
{ #category : 'accessing' }
InsPolicy >> hiredNonOwned: b [ hiredNonOwned := b ]
{ #category : 'accessing' }
InsPolicy >> id [ ^ id ]
{ #category : 'accessing' }
InsPolicy >> id: s [ id := s ]
{ #category : 'accessing' }
InsPolicy >> line [ ^ line ]
{ #category : 'accessing' }
InsPolicy >> line: s [ line := s ]
{ #category : 'accessing' }
InsPolicy >> multiPolicy [ ^ multiPolicy ]
{ #category : 'accessing' }
InsPolicy >> multiPolicy: b [ multiPolicy := b ]
{ #category : 'accessing' }
InsPolicy >> scheduleMod [ ^ scheduleMod ]
{ #category : 'accessing' }
InsPolicy >> scheduleMod: n [ scheduleMod := n ]
{ #category : 'accessing' }
InsPolicy >> state [ ^ state ]
{ #category : 'accessing' }
InsPolicy >> state: s [ state := s ]
{ #category : 'accessing' }
InsPolicy >> territory [ ^ territory ]
{ #category : 'accessing' }
InsPolicy >> territory: s [ territory := s ]
{ #category : 'accessing' }
InsPolicy >> waiver [ ^ waiver ]
{ #category : 'accessing' }
InsPolicy >> waiver: b [ waiver := b ]
{ #category : 'accessing' }
InsPolicy >> yearsInBusiness [ ^ yearsInBusiness ]
{ #category : 'accessing' }
InsPolicy >> yearsInBusiness: n [ yearsInBusiness := n ]
