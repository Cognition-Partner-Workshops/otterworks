"Load the InsRating Tonel package from the directory named by INSRATING_SRC."
| src |
src := (Smalltalk os environment at: 'INSRATING_SRC') asFileReference.
(TonelReader on: src fileName: 'InsRating') version load.
