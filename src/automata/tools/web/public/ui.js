import{a as v,b as g,c as y,d as w,e as A,f as E,g as T,h as $,i as k,j as C,k as R,l as _,m as F,n as z,o as N,p as q,q as O,r as j,s as M,t as P,u as i,v as S,w as I}from"./chunk-JBXPKTT7.js";var c=`
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
`;function h(o){let{accent:e,accentText:t,focus:r}=o.roles;return`& > button { background: ${e}; color: ${t}; }
    & > button:focus-visible { outline-color: ${r}; }`}var s=class extends i{static get observedAttributes(){return["disabled","type"]}control=document.createElement("button");connectedCallback(){if(this.control.parentNode!==this){for(;this.firstChild;)this.control.append(this.firstChild);this.append(this.control)}this.sync(),super.connectedCallback()}attributeChangedCallback(){this.sync()}get disabled(){return this.hasAttribute("disabled")}set disabled(e){this.toggleAttribute("disabled",e)}get type(){return this.control.type}set type(e){this.setAttribute("type",e)}focus(e){this.control.focus(e)}sync(){this.control.disabled=this.disabled;let e=this.getAttribute("type");this.control.type=e==="submit"||e==="reset"?e:"button"}themedStyle(e){return h(e)}};s.css=c;s.define("ui-button");var m=`
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
`;function p(o){let{surface:e,text:t,border:r}=o.roles;return`background: ${e}; color: ${t}; border-color: ${r};`}var n=class extends i{themedStyle(e){return p(e)}};n.css=m;n.define("ui-card");var u=`
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
`;function b(o){let{surface:e,text:t,border:r,mutedText:l,error:a,errorBorder:f,focus:x}=o.roles;return`color: ${t};
    & > input { color: ${t}; background: ${e}; border-color: ${r}; }
    & > input[aria-invalid="true"] { border-color: ${f}; }
    & > input:focus-visible { outline-color: ${x}; }
    & > .field-help { color: ${l}; }
    & > .field-error { color: ${a}; }`}var B=0,d=class extends i{static get observedAttributes(){return["label","help","error","disabled","required","type","name","placeholder","autocomplete","value"]}control=document.createElement("input");labelElement=document.createElement("label");helpElement=document.createElement("div");errorElement=document.createElement("div");fieldId=`ui-field-${++B}`;connectedCallback(){this.control.parentNode!==this&&(this.control.id=this.fieldId,this.labelElement.htmlFor=this.fieldId,this.helpElement.id=`${this.fieldId}-help`,this.helpElement.className="field-help",this.errorElement.id=`${this.fieldId}-error`,this.errorElement.className="field-error",this.append(this.labelElement,this.control,this.helpElement,this.errorElement)),this.sync(),super.connectedCallback()}attributeChangedCallback(e,t,r){e==="value"&&t!==r&&(this.control.value=r??""),this.sync()}get value(){return this.control.value}set value(e){this.control.value=e}get disabled(){return this.hasAttribute("disabled")}set disabled(e){this.toggleAttribute("disabled",e)}focus(e){this.control.focus(e)}sync(){this.labelElement.textContent=this.getAttribute("label")??"";let e=this.getAttribute("help")??"",t=this.getAttribute("error")??"";this.helpElement.textContent=e,this.errorElement.textContent=t,this.helpElement.hidden=!e,this.errorElement.hidden=!t,this.control.disabled=this.disabled,this.control.required=this.hasAttribute("required");for(let l of["type","name","placeholder","autocomplete"]){let a=this.getAttribute(l);a===null?this.control.removeAttribute(l):this.control.setAttribute(l,a)}let r=[e&&`${this.fieldId}-help`,t&&`${this.fieldId}-error`].filter(Boolean);r.length?this.control.setAttribute("aria-describedby",r.join(" ")):this.control.removeAttribute("aria-describedby"),t?this.control.setAttribute("aria-invalid","true"):this.control.removeAttribute("aria-invalid")}themedStyle(e){return b(e)}};d.css=u;d.define("ui-field");export{g as Adapter,i as Base,s as Button,n as Card,S as CodeBlock,d as Field,I as Markdown,F as ThemeRef,z as appTheme,M as bindTheme,j as clearTheme,R as color,k as colorAnchors,N as createTheme,v as css,T as culori,E as html,q as nearestTheme,y as nextTick,C as palette,w as reactive,_ as semanticRoles,O as setTheme,$ as shades,P as themeDiagnostics,A as watch};
