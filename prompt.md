The 3d selector of filter atoms chirality node opened from clicking button does not work correctly. It will display the ligand pdb even if it does not receive an input, and it cannot click to select atoms. However the poped up selector work correctly.
GLModel.ts:1470 Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'symmetries')
at renderViewer (index.vue:1432:10)
this error still present
The pdb viewer still cannot display RFdiffusion3 SM binder's outputs as a middle result. However the Rf3 pdb viewer work correctly
