1. When it is error state when archive is avaliable, make the color error color. Now it is green.
2. When the Batch Protein with Ligand output of RFDiffusion3 SM Binder are connect to two Nodes:Ligand MPNN and a PDB Viewer, PDB viewer cannot display the results correctly. (It displays nothing)
3. In all the selectors or viewers, do not display anything if the node has not received an input. (For stucking nodes' selector, do not let users pre-select with 3d viewer. For pdb viewers, make "Files" option empty if it hasn't received an input).
4. Change the issues bar for displaying the last 4 stderr line instead of 1.
5. The MANUAL sign overlaps with the three dots.
6. the console outputs the following when the second consecutive manual selector is popping up, but the second selector correctly pops up.
   installHook.js:1 [Vue warn]: Unhandled error during execution of native event handler
   at <Index onVnodeUnmounted=fn<onVnodeUnmounted> ref=Ref< Proxy(Object) {**v_skip: true}[[Handler]]: Object[[Target]]: Proxy(Object)[[IsRevoked]]: false > >
   at <RouteProvider key="/" vnode= {**v_isVNode: true, **v_skip: true, type: {…}, props: {…}, key: null, …}anchor: nullappContext: nullchildren: nullcomponent: nullctx: {uid: 3, vnode: {…}, type: {…}, parent: {…}, appContext: {…}, …}dirs: nulldynamicChildren: nulldynamicProps: nullel: nullkey: nullpatchFlag: 0props: {ref: RefImpl, onVnodeUnmounted: ƒ}ref: {i: {…}, r: RefImpl, k: undefined, f: false}scopeId: nullshapeFlag: 4slotScopeIds: nullssContent: nullssFallback: nullstaticCount: 0suspense: nulltarget: nulltargetAnchor: nulltargetStart: nulltransition: nulltype: {**name: 'index', **hmrId: '02281a80', **file: '/opt/FoundryUI/frontend/app/pages/index.vue', setup: ƒ, render: ƒ}**v_isVNode: true**v_skip: true[[Prototype]]: Object route= {fullPath: '/?session=session_61d1fe20db864f3a8c3891bae8337671', hash: '', query: {…}, name: 'index', path: '/', …}fullPath: "/?session=session_61d1fe20db864f3a8c3891bae8337671"hash: ""href: "/?session=session_61d1fe20db864f3a8c3891bae8337671"matched: [{…}]meta: Proxy(Object) {}name: "index"params: {}path: "/"query: {session: 'session_61d1fe20db864f3a8c3891bae8337671'}redirectedFrom: undefined[[Prototype]]: Object ... >
   at <RouterView name=undefined route=undefined >
   at <NuxtPage >
   at <App key=4 >
   at <NuxtRoot>
   index.vue:593 Uncaught (in promise) TypeError: Cannot read properties of null (reading 'nodeId')
   at submitRuntimeInput (index.vue:593:45)
   submitRuntimeInput @ index.vue:593
