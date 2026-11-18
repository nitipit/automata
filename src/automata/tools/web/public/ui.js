import{A as h,B as q,C as N,D as z,a as w,b as E,c as T,d as $,e as k,f as S,g as D,h as R,i as B,j as _,k as F,l as G,m as H,n as J,o as K,p as L,q as Q,r as U,s as W,t as X,u as n,v as I,w as s,y as l,z as p}from"./chunk-AZBAMOWI.js";import"./chunk-5TBO732O.js";var u=`
  display: inline-block;
  max-width: 100%;
  & > button {
    box-sizing: border-box;
    max-width: 100%;
    min-height: 2.5rem;
    padding: 0.55rem 0.9rem;
    border: 1px solid transparent;
    border-radius: 0.5rem;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    overflow-wrap: anywhere;
  }
  & > button:disabled { cursor: not-allowed; opacity: 0.6; }
  & > button:focus-visible { outline: 3px solid; outline-offset: 2px; }
`;function b(r){let{accent:e,accentText:o,focus:t}=r.roles;return`& > button { background: ${e}; color: ${o}; }
    & > button:focus-visible { outline-color: ${t}; }`}var d=class extends n{static get create(){return O}static get observedAttributes(){return["disabled","type"]}control=document.createElement("button");connectedCallback(){if(this.control.parentNode!==this){for(;this.firstChild;)this.control.append(this.firstChild);this.append(this.control)}this.sync(),super.connectedCallback()}attributeChangedCallback(){this.sync()}get disabled(){return this.hasAttribute("disabled")}set disabled(e){this.toggleAttribute("disabled",e)}get type(){return this.control.type}set type(e){this.setAttribute("type",e)}focus(e){this.control.focus(e)}sync(){this.control.disabled=this.disabled;let e=this.getAttribute("type");this.control.type=e==="submit"||e==="reset"?e:"button"}themedStyle(e){return b(e)}};d.css=u;d.define("ui-button");var O=s("ui-button",d,(r,e,o)=>{let t=l(e,"type");(t==="button"||t==="submit"||t==="reset")&&(r.type=t),r.disabled=p(e,"disabled")??!1,r.append(l(e,"text")??"",...o)});var f=`
  display: block;
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  padding: 1rem;
  border: 1px solid;
  border-radius: 0.75rem;
  overflow-wrap: anywhere;
  & > :first-child { margin-top: 0; }
  & > :last-child { margin-bottom: 0; }
`;function g(r){let{surface:e,text:o,border:t}=r.roles;return`background: ${e}; color: ${o}; border-color: ${t};`}var a=class extends n{static get create(){return j}themedStyle(e){return g(e)}};a.css=f;a.define("ui-card");var j=s("ui-card",a,(r,e,o)=>{let t=l(e,"label");t!==void 0&&r.setAttribute("aria-label",t),r.append(...o)});var x=`
  display: grid;
  min-width: 0;
  gap: 0.35rem;
  & > label { font-weight: 600; }
  & > input {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 2.5rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid;
    border-radius: 0.4rem;
    font: inherit;
  }
  & > input:focus-visible { outline: 3px solid; outline-offset: 2px; }
  & > input:disabled { opacity: 0.6; cursor: not-allowed; }
  & > .field-help, & > .field-error { font-size: 0.875em; overflow-wrap: anywhere; }
  & > [hidden] { display: none; }
`;function y(r){let{surface:e,text:o,border:t,mutedText:i,error:m,errorBorder:A,focus:C}=r.roles;return`color: ${o};
    & > input { color: ${o}; background: ${e}; border-color: ${t}; }
    & > input[aria-invalid="true"] { border-color: ${A}; }
    & > input:focus-visible { outline-color: ${C}; }
    & > .field-help { color: ${i}; }
    & > .field-error { color: ${m}; }`}var v=["label","help","error","type","name","placeholder","autocomplete","value"],P=0,c=class extends n{static get create(){return M}static get observedAttributes(){return[...v,"disabled","required"]}control=document.createElement("input");labelElement=document.createElement("label");helpElement=document.createElement("div");errorElement=document.createElement("div");fieldId=`ui-field-${++P}`;connectedCallback(){this.control.parentNode!==this&&(this.control.id=this.fieldId,this.labelElement.htmlFor=this.fieldId,this.helpElement.id=`${this.fieldId}-help`,this.helpElement.className="field-help",this.errorElement.id=`${this.fieldId}-error`,this.errorElement.className="field-error",this.append(this.labelElement,this.control,this.helpElement,this.errorElement)),this.sync(),super.connectedCallback()}attributeChangedCallback(e,o,t){e==="value"&&o!==t&&(this.control.value=t??""),this.sync()}get value(){return this.control.value}set value(e){this.control.value=e}get disabled(){return this.hasAttribute("disabled")}set disabled(e){this.toggleAttribute("disabled",e)}focus(e){this.control.focus(e)}sync(){this.labelElement.textContent=this.getAttribute("label")??"";let e=this.getAttribute("help")??"",o=this.getAttribute("error")??"";this.helpElement.textContent=e,this.errorElement.textContent=o,this.helpElement.hidden=!e,this.errorElement.hidden=!o,this.control.disabled=this.disabled,this.control.required=this.hasAttribute("required");for(let i of["type","name","placeholder","autocomplete"]){let m=this.getAttribute(i);m===null?this.control.removeAttribute(i):this.control.setAttribute(i,m)}let t=[e&&`${this.fieldId}-help`,o&&`${this.fieldId}-error`].filter(Boolean);t.length?this.control.setAttribute("aria-describedby",t.join(" ")):this.control.removeAttribute("aria-describedby"),o?this.control.setAttribute("aria-invalid","true"):this.control.removeAttribute("aria-invalid")}themedStyle(e){return y(e)}};c.css=x;c.define("ui-field");var M=s("ui-field",c,(r,e,o)=>{h("ui-field",o);for(let t of v){let i=l(e,t);i!==void 0&&r.setAttribute(t,i)}r.disabled=p(e,"disabled")??!1,r.toggleAttribute("required",p(e,"required")??!1)});export{E as Adapter,n as Base,d as Button,a as Card,N as CodeBlock,c as Field,z as Markdown,q as Select,H as ThemeRef,J as appTheme,W as bindTheme,U as clearTheme,F as color,B as colorAnchors,I as createComponent,K as createTheme,w as css,D as culori,S as html,L as nearestTheme,T as nextTick,_ as palette,$ as reactive,G as semanticRoles,Q as setTheme,R as shades,X as themeDiagnostics,k as watch};
