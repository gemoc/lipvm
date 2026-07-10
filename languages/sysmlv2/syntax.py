"""Definition of meta model 'sysml'."""
from functools import partial
import pyecore.ecore as Ecore
from pyecore.ecore import *

from core.language import AbstractSyntaxElement, RuntimeState

from core.operation import operation

# Aliased (not `from ... import *`) because the metamodel already declares
# its own `StateUsage` class below; `rt.StateUsage` keeps the runtime
# registry's StateUsage unambiguous from the AST's.
from languages.sysmlv2 import runtime as rt
from languages.sysmlv2.sysml_utility_classes import qualified_name
from languages.sysmlv2.kerml_libraries.kerml_library_index import resolve_kerml_library_name


# --- Hand-written interpreter helpers -------------------------------------
#
# Small AST-navigation helpers shared by evaluate() methods below (e.g.
# Namespace, PerformActionUsage). They read pyecoregen's plain, non-derived
# containment features (ownedRelationship / ownedRelatedElement) directly
# instead of the many derived convenience properties this generated module
# leaves as `raise NotImplementedError(...)`.

def _feature_type(feature):
    """Returns the AST type node from `feature`'s FeatureTyping relationship, if any."""
    for relationship in feature.ownedRelationship:
        if isinstance(relationship, FeatureTyping):
            return relationship.type
    return None


def _owned_by_kind(element, kind):
    """Yields the ownedRelatedElement(s) of each of `element`'s ownedRelationship of type `kind`."""
    for relationship in element.ownedRelationship:
        if isinstance(relationship, kind):
            yield from relationship.ownedRelatedElement


def _bound_value(feature):
    """Returns the AST literal/expression node bound to `feature` via a FeatureValue, if any."""
    for value in _owned_by_kind(feature, FeatureValue):
        return value
    return None


def _nearest_ancestor(element, kind):
    """Walks up `element`'s containment chain and returns the nearest
    ancestor of type `kind`, or None if there isn't one before the root."""
    container = element.eContainer()
    while container is not None and not isinstance(container, kind):
        container = container.eContainer()
    return container


def _formal_parameters(behavior):
    """Returns the owned features of `behavior` that declare a direction
    (in/inout/out) — i.e. its formal parameters.

    Checked via eIsSet() rather than `feature.direction is not None`: pyecore's
    generated `direction` EAttribute (unlike e.g. isComposite/isConstant) has
    no default_value=None, so an instance that never sets it reads back as
    FeatureDirectionKind's first literal ('in') instead of None — eIsSet() is
    the only way to tell "explicitly declared in" apart from "never set".
    """
    return [
        feature for feature in _owned_by_kind(behavior, FeatureMembership)
        if feature.eIsSet('direction')
    ]


def _populate_parameters(record, behavior):
    """Appends a runtime Parameter onto `record` for each formal parameter of `behavior`.

    Shared by the ActionDef and StateDef branches of evaluate() below, since
    StateDefinition extends ActionDefinition and both carry formal parameters.
    """
    for feature in _formal_parameters(behavior):
        record.parameters.append(rt.Parameter(
            declared_name=feature.declaredName,
            qualified_name=qualified_name(feature),
            type=_build_type_ref(_feature_type(feature)),
        ))


def _subaction(state_definition, kind):
    """Returns the entry/do/exit PerformActionUsage AST node of a StateDefinition, if any.

    `kind` is a plain string ('entry'/'do'/'exit'); relationship.kind is an
    EEnumLiteral, which pyecore doesn't compare equal to a string, hence str().
    """
    for relationship in state_definition.ownedRelationship:
        if isinstance(relationship, StateSubactionMembership) and str(relationship.kind) == kind:
            for element in relationship.ownedRelatedElement:
                return element
    return None


def _transition_source(transition_usage):
    """Returns the AST node `transition_usage` fires out of — a StateUsage
    substate (e.g. Idle), or a StateDef's own entry PerformActionUsage for
    the unconditional transition fired right after entry completes.

    Read off the plain Membership every TransitionUsage carries alongside
    its SuccessionAsUsage (not a FeatureMembership/EndFeatureMembership/etc,
    which all subclass OwningMembership instead).
    """
    for relationship in transition_usage.ownedRelationship:
        if isinstance(relationship, Membership) and not isinstance(relationship, OwningMembership):
            return relationship.memberElement
    return None


def _transition_target(transition_usage):
    """Returns the StateUsage AST node `transition_usage` fires into: the
    SuccessionAsUsage end identified by a ReferenceSubsetting. (The source
    end is left unlabeled in the XMI — _transition_source covers that case
    instead.)
    """
    for succession in _owned_by_kind(transition_usage, OwningMembership):
        if not isinstance(succession, SuccessionAsUsage):
            continue
        for end_feature in _owned_by_kind(succession, EndFeatureMembership):
            for relationship in end_feature.ownedRelationship:
                if isinstance(relationship, ReferenceSubsetting):
                    return relationship.referencedFeature
    return None


def _transition_trigger_action(transition_usage):
    """Returns the AcceptActionUsage AST node that's `transition_usage`'s
    trigger, if any.

    Identified structurally (child type) rather than via the sibling
    TransitionFeatureMembership's `kind`: the exporter doesn't reliably set
    kind='effect' on the other membership (same defaulted-EEnum landmine
    _formal_parameters works around for `direction`), so `kind` alone can't
    be trusted to tell trigger from effect.
    """
    for feature in _owned_by_kind(transition_usage, TransitionFeatureMembership):
        if isinstance(feature, AcceptActionUsage):
            return feature
    return None


def _transition_effect_action(transition_usage):
    """Returns the PerformActionUsage AST node performed when
    `transition_usage` fires, if any — identified structurally, for the
    same reason as _transition_trigger_action.
    """
    for feature in _owned_by_kind(transition_usage, TransitionFeatureMembership):
        if isinstance(feature, PerformActionUsage):
            return feature
    return None


def _default_transition(state_definition):
    """Returns the TransitionUsage AST node for the unconditional/completion
    transition fired right after `state_definition`'s own entry action, if
    any — the one TransitionUsage directly owned by it with no trigger.
    """
    for feature in _owned_by_kind(state_definition, FeatureMembership):
        if isinstance(feature, TransitionUsage) and _transition_trigger_action(feature) is None:
            return feature
    return None


def _build_actual_action(perform_action_usage):
    """Builds an ActualAction runtime record from a PerformActionUsage AST
    node (e.g. pEntry performing Print): the ActionDef it performs (a bare
    Reference, deferred the same way as _build_reference) and its bound
    call-site arguments.
    """
    if perform_action_usage is None:
        return None
    arguments = [
        rt.Argument(
            declared_name=feature.declaredName,
            qualified_name=qualified_name(feature),
            value=_bound_value(feature),
        )
        for feature in _owned_by_kind(perform_action_usage, FeatureMembership)
        if _bound_value(feature) is not None
    ]
    return rt.ActualAction(
        action_def=_build_reference(_feature_type(perform_action_usage), rt.ActionDef.__name__),
        arguments=arguments,
    )


def _build_transition(transition_usage):
    """Builds a Transition runtime record from a TransitionUsage AST node.

    `source`/`target` are bare References (see _build_reference); `source`
    stays None when the transition's owning context isn't itself a
    StateUsage (e.g. a StateDef's own entry-completion transition, whose
    source is the entry action rather than a substate).
    """
    if transition_usage is None:
        return None
    source = _transition_source(transition_usage)
    return rt.Transition(
        definition=transition_usage,
        source=_build_reference(source, rt.StateUsage.__name__) if isinstance(source, StateUsage) else None,
        effect=_build_actual_action(_transition_effect_action(transition_usage)),
        target=_build_reference(_transition_target(transition_usage), rt.StateUsage.__name__),
    )


def _build_type_ref(type_node):
    """Builds the TypeRef describing a Parameter's type from `type_node` (the
    AST node/proxy found via a feature's FeatureTyping relationship).

    This only classifies `kind` from `type_node`'s own AST class (or, for a
    KerML library scalar, from the local library index) — it never resolves
    the actual runtime Definition, so it needs no LookupTable and doesn't
    care whether the target Definition has been registered yet. For
    anything but a scalar, `reference_type` is a bare Reference carrying
    just the target's qualified name; looking it up against the right
    LookupTable to get the actual ActionDef/ItemDef/StateDef is left to
    whoever dereferences it later.
    """
    custom_type = None
    if type_node is None:
        return None

    if isinstance(type_node, EProxy) and not type_node.resolved:
        name = resolve_kerml_library_name(type_node._proxy_path)
        scalar_type = rt._SCALAR_TYPE_BY_NAME.get(name) if name else None
        return rt.TypeRef(kind=rt.TypeKind.SCALAR, scalar_type=scalar_type)

    # StateDefinition/PartDefinition extend ActionDefinition/ItemDefinition
    # respectively in the metamodel, so the more specific check comes first.
    if isinstance(type_node, StateDefinition):
        kind = rt.TypeKind.CUSTOM
    elif isinstance(type_node, ActionDefinition):
        kind = rt.TypeKind.ACTION
        custom_type = rt.ActionDef.__name__
    elif isinstance(type_node, PartDefinition):
        kind = rt.TypeKind.PART
    elif isinstance(type_node, ItemDefinition):
        kind = rt.TypeKind.ITEM
        custom_type = rt.ItemDef.__name__
    elif isinstance(type_node, EnumerationDefinition):
        kind = rt.TypeKind.ENUM

    else:
        kind = rt.TypeKind.UNKNOWN

    return rt.TypeRef(kind=kind, reference_type=rt.Reference(qualified_name=qualified_name(type_node),
                                                             reference_type=custom_type))


def _build_reference(type_node, type_name_for_reference):
    """Builds a bare Reference carrying just `type_node`'s qualified name —
    like _build_type_ref's reference_type, this never resolves the actual
    runtime Definition, so it needs no LookupTable and doesn't care whether
    the target has been registered yet. Looking it up against the right
    LookupTable to get the actual Definition is left to whoever
    dereferences it later.
    """
    if type_node is None:
        return None
    if isinstance(type_node, EProxy) and not type_node.resolved:
        return None
    return rt.Reference(qualified_name=qualified_name(type_node), reference_type=type_name_for_reference)


name = 'sysml'
nsURI = 'https://www.omg.org/spec/SysML/20250201'
nsPrefix = 'sysml'

eClass = EPackage(name=name, nsURI=nsURI, nsPrefix=nsPrefix)

eClassifiers = {}
getEClassifier = partial(Ecore.getEClassifier, searchspace=eClassifiers)
FeatureDirectionKind = EEnum('FeatureDirectionKind', literals=['in_', 'inout', 'out'])

PortionKind = EEnum('PortionKind', literals=['timeslice', 'snapshot'])

RequirementConstraintKind = EEnum('RequirementConstraintKind', literals=[
                                  'assumption', 'requirement'])

StateSubactionKind = EEnum('StateSubactionKind', literals=['entry', 'do', 'exit'])

TransitionFeatureKind = EEnum('TransitionFeatureKind', literals=['trigger', 'guard', 'effect'])

TriggerKind = EEnum('TriggerKind', literals=['when', 'at', 'after'])

VisibilityKind = EEnum('VisibilityKind', literals=['private', 'protected', 'public'])


class DerivedDocumentation(EDerivedCollection):
    pass


class DerivedOwnedannotation(EDerivedCollection):
    pass


class DerivedOwnedelement(EDerivedCollection):
    pass


class DerivedTextualrepresentation(EDerivedCollection):
    pass


@abstract
class Element(AbstractSyntaxElement, metaclass=MetaEClass):
    """<p>An <code>Element</code> is a constituent of a model that is uniquely identified relative to all other <code>Elements</code>. It can have <code>Relationships</code> with other <code>Elements</code>. Some of these <code>Relationships</code> might imply ownership of other <code>Elements</code>, which means that if an <code>Element</code> is deleted from a model, then so are all the <code>Elements</code> that it owns.</p>

ownedElement = ownedRelationship.ownedRelatedElement
owner = owningRelationship.owningRelatedElement
qualifiedName =
    if owningNamespace = null then null
    else if name <> null and 
        owningNamespace.ownedMember->
        select(m | m.name = name).indexOf(self) <> 1 then null
    else if owningNamespace.owner = null then escapedName()
    else if owningNamespace.qualifiedName = null or 
            escapedName() = null then null
    else owningNamespace.qualifiedName + '::' + escapedName()
    endif endif endif endif
documentation = ownedElement->selectByKind(Documentation)
ownedAnnotation = ownedRelationship->
    selectByKind(Annotation)->
    select(a | a.annotatedElement = self)
name = effectiveName()
ownedRelationship->exists(isImplied) implies isImpliedIncluded
isLibraryElement = libraryNamespace() <> null

shortName = effectiveShortName()
owningNamespace =
    if owningMembership = null then null
    else owningMembership.membershipOwningNamespace
    endif
textualRepresentation = ownedElement->selectByKind(TextualRepresentation)"""
    aliasIds = EAttribute(eType=EString, unique=True, derived=False, changeable=True, upper=-1)
    declaredName = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    declaredShortName = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    elementId = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    isImpliedIncluded = EAttribute(eType=EBoolean, unique=True,
                                   derived=False, changeable=True, default_value=False)
    _isLibraryElement = EAttribute(eType=EBoolean, unique=True, derived=True,
                                   changeable=True, name='isLibraryElement', transient=True)
    _name = EAttribute(eType=EString, unique=True, derived=True,
                       changeable=True, name='name', transient=True)
    _qualifiedName = EAttribute(eType=EString, unique=True, derived=True,
                                changeable=True, name='qualifiedName', transient=True)
    _shortName = EAttribute(eType=EString, unique=True, derived=True,
                            changeable=True, name='shortName', transient=True)
    documentation = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedDocumentation)
    ownedAnnotation = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedannotation)
    ownedElement = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedOwnedelement)
    ownedRelationship = EReference(ordered=True, unique=True,
                                   containment=True, derived=False, upper=-1)
    _owner = EReference(ordered=False, unique=True, containment=False,
                        derived=True, name='owner', transient=True)
    _owningMembership = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='owningMembership', transient=True)
    _owningNamespace = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='owningNamespace', transient=True)
    owningRelationship = EReference(ordered=False, unique=True, containment=False, derived=False)
    textualRepresentation = EReference(ordered=True, unique=True, containment=False,
                                       derived=True, upper=-1, transient=True, derived_class=DerivedTextualrepresentation)

    @property
    def isLibraryElement(self):
        raise NotImplementedError('Missing implementation for isLibraryElement')

    @isLibraryElement.setter
    def isLibraryElement(self, value):
        raise NotImplementedError('Missing implementation for isLibraryElement')

    @property
    def name(self):
        raise NotImplementedError('Missing implementation for name')

    @name.setter
    def name(self, value):
        raise NotImplementedError('Missing implementation for name')

    @property
    def owner(self):
        raise NotImplementedError('Missing implementation for owner')

    @owner.setter
    def owner(self, value):
        raise NotImplementedError('Missing implementation for owner')

    @property
    def owningMembership(self):
        raise NotImplementedError('Missing implementation for owningMembership')

    @owningMembership.setter
    def owningMembership(self, value):
        raise NotImplementedError('Missing implementation for owningMembership')

    @property
    def owningNamespace(self):
        raise NotImplementedError('Missing implementation for owningNamespace')

    @owningNamespace.setter
    def owningNamespace(self, value):
        raise NotImplementedError('Missing implementation for owningNamespace')

    @property
    def qualifiedName(self):
        raise NotImplementedError('Missing implementation for qualifiedName')

    @qualifiedName.setter
    def qualifiedName(self, value):
        raise NotImplementedError('Missing implementation for qualifiedName')

    @property
    def shortName(self):
        raise NotImplementedError('Missing implementation for shortName')

    @shortName.setter
    def shortName(self, value):
        raise NotImplementedError('Missing implementation for shortName')

    def __init__(self, *, aliasIds=None, declaredName=None, declaredShortName=None, documentation=None, elementId=None, isImpliedIncluded=None, isLibraryElement=None, name=None, ownedAnnotation=None, ownedElement=None, ownedRelationship=None, owner=None, owningMembership=None, owningNamespace=None, owningRelationship=None, qualifiedName=None, shortName=None, textualRepresentation=None):
        # if kwargs:
        #    raise AttributeError('unexpected arguments: {}'.format(kwargs))

        super().__init__()

        if aliasIds:
            self.aliasIds.extend(aliasIds)

        if declaredName is not None:
            self.declaredName = declaredName

        if declaredShortName is not None:
            self.declaredShortName = declaredShortName

        if elementId is not None:
            self.elementId = elementId

        if isImpliedIncluded is not None:
            self.isImpliedIncluded = isImpliedIncluded

        if isLibraryElement is not None:
            self.isLibraryElement = isLibraryElement

        if name is not None:
            self.name = name

        if qualifiedName is not None:
            self.qualifiedName = qualifiedName

        if shortName is not None:
            self.shortName = shortName

        if documentation:
            self.documentation.extend(documentation)

        if ownedAnnotation:
            self.ownedAnnotation.extend(ownedAnnotation)

        if ownedElement:
            self.ownedElement.extend(ownedElement)

        if ownedRelationship:
            self.ownedRelationship.extend(ownedRelationship)

        if owner is not None:
            self.owner = owner

        if owningMembership is not None:
            self.owningMembership = owningMembership

        if owningNamespace is not None:
            self.owningNamespace = owningNamespace

        if owningRelationship is not None:
            self.owningRelationship = owningRelationship

        if textualRepresentation:
            self.textualRepresentation.extend(textualRepresentation)

    def effectiveName(self):
        """<p>Return an effective <code>name</code> for this <code>Element</code>. By default this is the same as its <code>declaredName</code>.</p>
declaredName"""
        raise NotImplementedError('operation effectiveName(...) not yet implemented')

    def effectiveShortName(self):
        """<p>Return an effective <code>shortName</code> for this <code>Element</code>. By default this is the same as its <code>declaredShortName</code>.</p>
declaredShortName"""
        raise NotImplementedError('operation effectiveShortName(...) not yet implemented')

    def escapedName(self):
        """<p>Return <code>name</code>, if that is not null, otherwise the <code>shortName</code>, if that is not null, otherwise null. If the returned value is non-null, it is returned as-is if it has the form of a basic name, or, otherwise, represented as a restricted name according to the lexical structure of the KerML textual notation (i.e., surrounded by single quote characters and with special characters escaped).</p>"""
        raise NotImplementedError('operation escapedName(...) not yet implemented')

    def libraryNamespace(self):
        """<p>By default, return the library Namespace of the <code>owningRelationship</code> of this Element, if it has one.</p>
if owningRelationship <> null then owningRelationship.libraryNamespace()
else null endif"""
        raise NotImplementedError('operation libraryNamespace(...) not yet implemented')

    def path(self):
        """<p>Return a unique description of the location of this <code>Element</code> in the containment structure rooted in a root <code>Namespace</code>. If the <code>Element</code> has a non-null <code>qualifiedName</code>, then return that. Otherwise, if it has an <code>owningRelationship</code>, then return the string constructed by appending to the <code>path</code> of it's <code>owningRelationship</code> the character <code>/</code> followed by the string representation of its position in the list of <code>ownedRelatedElements</code> of the <code>owningRelationship</code> (indexed starting at 1). Otherwise, return the empty string.</p>

<p>(Note that this operation is overridden for <code>Relationships</code> to use <code>owningRelatedElement</code> when appropriate.)</p>
if qualifiedName <> null then qualifiedName
else if owningRelationship <> null then
    owningRelationship.path() + '/' + 
    owningRelationship.ownedRelatedElement->indexOf(self).toString()
    -- A position index shall be converted to a decimal string representation 
    -- consisting of only decimal digits, with no sign, leading zeros or leading 
    -- or trailing whitespace.
else ''
endif endif"""
        raise NotImplementedError('operation path(...) not yet implemented')

class DerivedAnnotatedelement(EDerivedCollection):
    pass


class DerivedAnnotation(EDerivedCollection):
    pass


class DerivedOwnedannotatingrelationship(EDerivedCollection):
    pass


class AnnotatingElement(Element):
    """<p>An <code>AnnotatingElement</code> is an <code>Element</code> that provides additional description of or metadata on some other <code>Element</code>. An <code>AnnotatingElement</code> is either attached to its <code>annotatedElements</code> by <code>Annotation</code> <code>Relationships</code>, or it implicitly annotates its <code>owningNamespace</code>.</p>

annotatedElement = 
 if annotation->notEmpty() then annotation.annotatedElement
 else Sequence{owningNamespace} endif
ownedAnnotatingRelationship = ownedRelationship->
    selectByKind(Annotation)->
    select(a | a.annotatedElement <> self)
annotation = 
    if owningAnnotatingRelationship = null then ownedAnnotatingRelationship
    else owningAnnotatingRelationship->prepend(owningAnnotatingRelationship)
    endif"""
    annotatedElement = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedAnnotatedelement)
    annotation = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedAnnotation)
    ownedAnnotatingRelationship = EReference(ordered=True, unique=True, containment=False,
                                             derived=True, upper=-1, transient=True, derived_class=DerivedOwnedannotatingrelationship)
    _owningAnnotatingRelationship = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='owningAnnotatingRelationship', transient=True)

    @property
    def owningAnnotatingRelationship(self):
        raise NotImplementedError('Missing implementation for owningAnnotatingRelationship')

    @owningAnnotatingRelationship.setter
    def owningAnnotatingRelationship(self, value):
        raise NotImplementedError('Missing implementation for owningAnnotatingRelationship')

    def __init__(self, *, annotatedElement=None, annotation=None, ownedAnnotatingRelationship=None, owningAnnotatingRelationship=None, **kwargs):

        super().__init__(**kwargs)

        if annotatedElement:
            self.annotatedElement.extend(annotatedElement)

        if annotation:
            self.annotation.extend(annotation)

        if ownedAnnotatingRelationship:
            self.ownedAnnotatingRelationship.extend(ownedAnnotatingRelationship)

        if owningAnnotatingRelationship is not None:
            self.owningAnnotatingRelationship = owningAnnotatingRelationship


class DerivedImportedmembership(EDerivedCollection):
    pass


class DerivedMember(EDerivedCollection):
    pass


class DerivedMembership(EDerivedCollection):
    pass


class DerivedOwnedimport(EDerivedCollection):
    pass


class DerivedOwnedmember(EDerivedCollection):
    pass


class DerivedOwnedmembership(EDerivedCollection):
    pass


class Namespace(Element):
    """<p>A <code>Namespace</code> is an <code>Element</code> that contains other <code>Elements</code>, known as its <code>members</code>, via <code>Membership</code> <code>Relationships</code> with those <code>Elements</code>. The <code>members</code> of a <code>Namespace</code> may be owned by the <code>Namespace</code>, aliased in the <code>Namespace</code>, or imported into the <code>Namespace</code> via <code>Import</code> <code>Relationships</code>.</p>

<p>A <code>Namespace</code> can provide names for its <code>members</code> via the <code>memberNames</code> and <code>memberShortNames</code> specified by the <code>Memberships</code> in the <code>Namespace</code>. If a <code>Membership</code> specifies a <code>memberName</code> and/or <code>memberShortName</code>, then those are names of the corresponding <code>memberElement</code> relative to the <code>Namespace</code>. For an <code>OwningMembership</code>, the <code>ownedMemberName</code> and <code>ownedMemberShortName</code> are given by the <code>Element</code> <code>name</code> and <code>shortName</code>. Note that the same <code>Element</code> may be the <code>memberElement</code> of multiple <code>Memberships</code> in a <code>Namespace</code> (though it may be owned at most once), each of which may define a separate alias for the <code>Element</code> relative to the <code>Namespace</code>.</p>

membership->forAll(m1 | 
    membership->forAll(m2 | 
        m1 <> m2 implies m1.isDistinguishableFrom(m2)))
member = membership.memberElement
ownedMember = ownedMembership->selectByKind(OwningMembership).ownedMemberElement
importedMembership = importedMemberships(Set{})
ownedImport = ownedRelationship->selectByKind(Import)
ownedMembership = ownedRelationship->selectByKind(Membership)"""
    importedMembership = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedImportedmembership)
    member = EReference(ordered=True, unique=True, containment=False, derived=True,
                        upper=-1, transient=True, derived_class=DerivedMember)
    membership = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedMembership)
    ownedImport = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedOwnedimport)
    ownedMember = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedOwnedmember)
    ownedMembership = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedmembership)

    def __init__(self, *, importedMembership=None, member=None, membership=None, ownedImport=None, ownedMember=None, ownedMembership=None, **kwargs):

        super().__init__(**kwargs)

        if importedMembership:
            self.importedMembership.extend(importedMembership)

        if member:
            self.member.extend(member)

        if membership:
            self.membership.extend(membership)

        if ownedImport:
            self.ownedImport.extend(ownedImport)

        if ownedMember:
            self.ownedMember.extend(ownedMember)

        if ownedMembership:
            self.ownedMembership.extend(ownedMembership)

    def importedMemberships(self, excluded=None):
        """<p>Derive the imported <code>Memberships</code> of this <code>Namespace</code> as the <code>importedMembership</code> of all <code>ownedImports</code>, excluding those Imports whose <code>importOwningNamespace</code> is in the <code>excluded</code> set, and excluding <code>Memberships</code> that have distinguisibility collisions with each other or with any <code>ownedMembership</code>.</p>

ownedImport.importedMemberships(excluded->including(self))"""
        raise NotImplementedError('operation importedMemberships(...) not yet implemented')

    def membershipsOfVisibility(self, visibility=None, excluded=None):
        """<p>If <code>visibility</code> is not null, return the <code>Memberships</code> of this <code>Namespace</code> with the given <code>visibility</code>, including <code>ownedMemberships</code> with the given <code>visibility</code> and <code>Memberships</code> imported with the given <code>visibility</code>. If <code>visibility</code> is null, return all <code>ownedMemberships</code> and imported <code>Memberships</code> regardless of visibility. When computing imported <code>Memberships</code>, ignore this <code>Namespace</code> and any <code>Namespaces</code> in the given <code>excluded</code> set.</p>
ownedMembership->
    select(mem | visibility = null or mem.visibility = visibility)->
    union(ownedImport->
        select(imp | visibility = null or imp.visibility = visibility).
        importedMemberships(excluded->including(self)))"""
        raise NotImplementedError('operation membershipsOfVisibility(...) not yet implemented')

    def namesOf(self, element=None):
        """<p>Return the names of the given <code>element</code> as it is known in this <code>Namespace</code>.</p>

let elementMemberships : Sequence(Membership) = 
    memberships->select(memberElement = element) in
memberships.memberShortName->
    union(memberships.memberName)->
    asSet()"""
        raise NotImplementedError('operation namesOf(...) not yet implemented')

    def qualificationOf(self, qualifiedName=None):
        """<p>Return a string with valid KerML syntax representing the qualification part of a given <code>qualifiedName</code>, that is, a qualified name with all the segment names of the given name except the last. If the given <code>qualifiedName</code> has only one segment, then return null.</p>
No OCL"""
        raise NotImplementedError('operation qualificationOf(...) not yet implemented')

    def resolve(self, qualifiedName=None):
        """<p>Resolve the given qualified name to the named <code>Membership</code> (if any), starting with this <code>Namespace</code> as the local scope. The qualified name string must conform to the concrete syntax of the KerML textual notation. According to the KerML name resolution rules every qualified name will resolve to either a single <code>Membership</code>, or to none.</p>

let qualification : String = qualificationOf(qualifiedName) in
let name : String = unqualifiedNameOf(qualifiedName) in
if qualification = null then resolveLocal(name)
else if qualification = '$' then  resolveGlobal(name)
else 
    let namespaceMembership : Membership = resolve(qualification) in
    if namespaceMembership = null or 
       not namespaceMembership.memberElement.oclIsKindOf(Namespace) 
    then null
    else 
        namespaceMembership.memberElement.oclAsType(Namespace).
        resolveVisible(name) 
    endif
endif endif"""
        raise NotImplementedError('operation resolve(...) not yet implemented')

    def resolveGlobal(self, qualifiedName=None):
        """<p>Resolve the given qualified name to the named <code>Membership</code> (if any) in the effective global <code>Namespace</code> that is the outermost naming scope. The qualified name string must conform to the concrete syntax of the KerML textual notation.</p>

No OCL"""
        raise NotImplementedError('operation resolveGlobal(...) not yet implemented')

    def resolveLocal(self, name=None):
        """<p>Resolve a simple <code>name</code> starting with this <code>Namespace</code> as the local scope, and continuing with containing outer scopes as necessary. However, if this <code>Namespace</code> is a root <code>Namespace</code>, then the resolution is done directly in global scope.</p>

if owningNamespace = null then resolveGlobal(name)
else
    let memberships : Membership = membership->
        select(memberShortName = name or memberName = name) in
    if memberships->notEmpty() then memberships->first()
    else owningNamespace.resolveLocal(name)
    endif
endif"""
        raise NotImplementedError('operation resolveLocal(...) not yet implemented')

    def resolveVisible(self, name=None):
        """<p>Resolve a simple name from the visible <code>Memberships</code> of this <code>Namespace</code>.</p>

let memberships : Sequence(Membership) =
    visibleMemberships(Set{}, false, false)->
    select(memberShortName = name or memberName = name) in
if memberships->isEmpty() then null
else memberships->first()
endif"""
        raise NotImplementedError('operation resolveVisible(...) not yet implemented')

    def unqualifiedNameOf(self, qualifiedName=None):
        """<p>Return the simple name that is the last segment name of the given <code>qualifiedName</code>. If this segment name has the form of a KerML unrestricted name, then "unescape" it by removing the surrounding single quotes and replacing all escape sequences with the specified character.</p>
No OCL"""
        raise NotImplementedError('operation unqualifiedNameOf(...) not yet implemented')

    def visibilityOf(self, mem=None):
        """<p>Returns this visibility of <code>mem</code> relative to this <code>Namespace</code>. If <code>mem</code> is an <code>importedMembership</code>, this is the <code>visibility</code> of its Import. Otherwise it is the <code>visibility</code> of the <code>Membership</code> itself.</p>

if importedMembership->includes(mem) then
    ownedImport->
        select(importedMemberships(Set{})->includes(mem)).
        first().visibility
else if memberships->includes(mem) then
    mem.visibility
else
    VisibilityKind::private
endif"""
        raise NotImplementedError('operation visibilityOf(...) not yet implemented')

    def visibleMemberships(self, excluded=None, isRecursive=None, includeAll=None):
        """<p>If <code>includeAll = true</code>, then return all the <code>Memberships</code> of this <code>Namespace</code>. Otherwise, return only the publicly visible <code>Memberships</code> of this <code>Namespace</code>, including <code>ownedMemberships</code> that have a <code>visibility</code> of <code>public</code> and <code>Memberships</code> imported with a <code>visibility</code> of <code>public</code>. If <code>isRecursive = true</code>, also recursively include all visible <code>Memberships</code> of any <code>public</code> owned <code>Namespaces</code>, or, if <code>IncludeAll = true</code>, all <code>Memberships</code> of all owned <code>Namespaces</code>. When computing imported <code>Memberships</code>, ignore this <code>Namespace</code> and any <code>Namespaces</code> in the given <code>excluded</code> set.</p>

let visibleMemberships : OrderedSet(Membership) = 
    if includeAll then membershipsOfVisibility(null, excluded)
    else membershipsOfVisibility(VisibilityKind::public, excluded)
    endif in
if not isRecursive then visibleMemberships
else visibleMemberships->union(ownedMember->
    selectAsKind(Namespace).
    select(includeAll or owningMembership.visibility = VisibilityKind::public)->
    visibleMemberships(excluded->including(self), true, includeAll))
endif
"""
        raise NotImplementedError('operation visibleMemberships(...) not yet implemented')

    @operation
    def evaluate(self, runtime: RuntimeState):

        # A single SysmlRuntimeState, one LookupTable per Definition kind,
        # keyed by qualified name, doubles as both the registry built up
        # below and the structure the rest of the AST resolves against.
        sysml_state = rt.SysmlRuntimeState(name="sysml")
        sysml_state.lookup_table_action_defs = rt.LookupTable()
        sysml_state.lookup_table_item_defs = rt.LookupTable()
        sysml_state.lookup_table_state_defs = rt.LookupTable()
        sysml_state.lookup_table_executable_state_usages = rt.LookupTable()

        action_defs = sysml_state.lookup_table_action_defs
        item_defs = sysml_state.lookup_table_item_defs
        state_defs = sysml_state.lookup_table_state_defs
        state_usages = sysml_state.lookup_table_executable_state_usages

        # Register every ActionDefinition/ItemDefinition/StateDefinition into
        # its LookupTable and wire up its own parameters/substates in the
        # same pass: Parameter.type no longer needs every other Definition
        # to already be registered (it only classifies `kind` from the AST
        # node itself and defers resolving the actual Definition to later),
        # so there's no forward reference left to wait out with a second
        # pass over self.eAllContents().
        for element in self.eAllContents():
            # StateDefinition extends1 ActionDefinition in the metamodel, so
            # it's checked first — otherwise it would be misclassified as a
            # plain ActionDef and never reach the StateDef branch below.
            if isinstance(element, StateDefinition):
                record = rt.StateDef(
                    declared_name=element.declaredName, qualified_name=qualified_name(element), definition=element)
                state_defs.set_reference(record.qualified_name, record)
                _populate_parameters(record, element)

                record.entry_action = _build_actual_action(_subaction(element, 'entry'))
                record.default_transition = _build_transition(_default_transition(element))

                # Two passes: substates must all exist before matching
                # transitions against them, since a transition's source can
                # appear before or after it among element's own features.
                substates_by_definition = {}
                for feature in _owned_by_kind(element, FeatureMembership):
                    if isinstance(feature, StateUsage):
                        substate = rt.StateUsage(
                            declared_name=feature.declaredName,
                            qualified_name=qualified_name(feature),
                            definition=feature,
                        )
                        record.substates.append(substate)
                        substates_by_definition[feature] = substate

                for feature in _owned_by_kind(element, FeatureMembership):
                    if isinstance(feature, TransitionUsage):
                        substate = substates_by_definition.get(_transition_source(feature))
                        if substate is not None:
                            substate.contained_transitions.append(_build_transition(feature))
            elif isinstance(element, ActionDefinition):
                record = rt.ActionDef(
                    declared_name=element.declaredName, qualified_name=qualified_name(element), definition=element)
                action_defs.set_reference(record.qualified_name, record)
                _populate_parameters(record, element)
            elif isinstance(element, ItemDefinition):
                record = rt.ItemDef(
                    declared_name=element.declaredName, qualified_name=qualified_name(element), definition=element)
                item_defs.set_reference(record.qualified_name, record)
            elif isinstance(element, StateUsage) and _nearest_ancestor(element, StateDefinition) is None:
                # A StateUsage declared outside any StateDefinition (e.g.
                # `main : MySimulationDefinition`) is an actual, independently
                # running instance of a state machine — unlike a
                # StateDefinition's own nested substates (Idle/Next above),
                # which are purely structural and never carry a type of their
                # own by modeling convention. Hence the distinct runtime
                # element (rt.ExecutableStateUsage vs. rt.StateUsage).
                record = rt.ExecutableStateUsage(
                    declared_name=element.declaredName, qualified_name=qualified_name(element), definition=element)
                # A bare Reference (qualified name only), not the resolved
                # StateDef — like Parameter.type/_build_type_ref, this never
                # touches state_defs, so it doesn't care whether the target
                # has been registered yet; dereferencing it against the
                # right LookupTable is left to whoever executes it later.
                record.state_def_origin = _build_reference(_feature_type(element), rt.StateDef.__name__)
                state_usages.set_reference(record.qualified_name, record)

        runtime.elements.append(sysml_state)


class DerivedRelatedelement(EDerivedCollection):
    pass


@abstract
class Relationship(Element):
    """<p>A <code>Relationship</code> is an <code>Element</code> that relates other <code>Element</code>. Some of its <code>relatedElements</code> may be owned, in which case those <code>ownedRelatedElements</code> will be deleted from a model if their <code>owningRelationship</code> is. A <code>Relationship</code> may also be owned by another <code>Element</code>, in which case the <code>ownedRelatedElements</code> of the <code>Relationship</code> are also considered to be transitively owned by the <code>owningRelatedElement</code> of the <code>Relationship</code>.</p>

<p>The <code>relatedElements</code> of a <code>Relationship</code> are divided into <code>source</code> and <code>target</code> <code>Elements</code>. The <code>Relationship</code> is considered to be directed from the <code>source</code> to the <code>target</code> <code>Elements</code>. An undirected <code>Relationship</code> may have either all <code>source</code> or all <code>target</code> <code>Elements</code>.</p>

<p>A &quot;relationship <code>Element</code>&quot; in the abstract syntax is generically any <code>Element</code> that is an instance of either <code>Relationship</code> or a direct or indirect specialization of <code>Relationship</code>. Any other kind of <code>Element</code> is a &quot;non-relationship <code>Element</code>&quot;. It is a convention of that non-relationship <code>Elements</code> are <em>only</em> related via reified relationship <code>Elements</code>. Any meta-associations directly between non-relationship <code>Elements</code> must be derived from underlying reified <code>Relationship</code>.</p>

relatedElement = source->union(target)"""
    isImplied = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    ownedRelatedElement = EReference(ordered=True, unique=True,
                                     containment=True, derived=False, upper=-1)
    owningRelatedElement = EReference(ordered=False, unique=True, containment=False, derived=False)
    relatedElement = EReference(ordered=True, unique=False, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedRelatedelement)
    source = EReference(ordered=True, unique=True, containment=False, derived=False, upper=-1)
    target = EReference(ordered=True, unique=True, containment=False, derived=False, upper=-1)

    def __init__(self, *, isImplied=None, ownedRelatedElement=None, owningRelatedElement=None, relatedElement=None, source=None, target=None, **kwargs):

        super().__init__(**kwargs)

        if isImplied is not None:
            self.isImplied = isImplied

        if ownedRelatedElement:
            self.ownedRelatedElement.extend(ownedRelatedElement)

        if owningRelatedElement is not None:
            self.owningRelatedElement = owningRelatedElement

        if relatedElement:
            self.relatedElement.extend(relatedElement)

        if source:
            self.source.extend(source)

        if target:
            self.target.extend(target)


class Annotation(Relationship):
    """<p>An <code>Annotation</code> is a Relationship between an <code>AnnotatingElement</code> and the <code>Element</code> that is annotated by that <code>AnnotatingElement</code>.</p>

(owningAnnotatedElement <> null) = (ownedAnnotatingElement <> null)
ownedAnnotatingElement <> null xor owningAnnotatingElement <> null
ownedAnnotatingElement =
    let ownedAnnotatingElements : Sequence(AnnotatingElement) = 
        ownedRelatedElement->selectByKind(AnnotatingElement) in
    if ownedAnnotatingElements->isEmpty() then null
    else ownedAnnotatingElements->first()
    endif
annotatingElement =
    if ownedAnnotatingElement <> null then ownedAnnotatingElement
    else owningAnnotatingElement
    endif"""
    annotatedElement = EReference(ordered=False, unique=True, containment=False, derived=False)
    _annotatingElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='annotatingElement', transient=True)
    _ownedAnnotatingElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedAnnotatingElement', transient=True)
    _owningAnnotatedElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='owningAnnotatedElement', transient=True)
    _owningAnnotatingElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='owningAnnotatingElement', transient=True)

    @property
    def annotatingElement(self):
        raise NotImplementedError('Missing implementation for annotatingElement')

    @annotatingElement.setter
    def annotatingElement(self, value):
        raise NotImplementedError('Missing implementation for annotatingElement')

    @property
    def ownedAnnotatingElement(self):
        raise NotImplementedError('Missing implementation for ownedAnnotatingElement')

    @ownedAnnotatingElement.setter
    def ownedAnnotatingElement(self, value):
        raise NotImplementedError('Missing implementation for ownedAnnotatingElement')

    @property
    def owningAnnotatedElement(self):
        raise NotImplementedError('Missing implementation for owningAnnotatedElement')

    @owningAnnotatedElement.setter
    def owningAnnotatedElement(self, value):
        raise NotImplementedError('Missing implementation for owningAnnotatedElement')

    @property
    def owningAnnotatingElement(self):
        raise NotImplementedError('Missing implementation for owningAnnotatingElement')

    @owningAnnotatingElement.setter
    def owningAnnotatingElement(self, value):
        raise NotImplementedError('Missing implementation for owningAnnotatingElement')

    def __init__(self, *, annotatedElement=None, annotatingElement=None, ownedAnnotatingElement=None, owningAnnotatedElement=None, owningAnnotatingElement=None, **kwargs):

        super().__init__(**kwargs)

        if annotatedElement is not None:
            self.annotatedElement = annotatedElement

        if annotatingElement is not None:
            self.annotatingElement = annotatingElement

        if ownedAnnotatingElement is not None:
            self.ownedAnnotatingElement = ownedAnnotatingElement

        if owningAnnotatedElement is not None:
            self.owningAnnotatedElement = owningAnnotatedElement

        if owningAnnotatingElement is not None:
            self.owningAnnotatingElement = owningAnnotatingElement


class Comment(AnnotatingElement):
    """<p>A <code>Comment</code> is an <code>AnnotatingElement</code> whose <code>body</code> in some way describes its <code>annotatedElements</code>.</p>
"""
    body = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    locale = EAttribute(eType=EString, unique=True, derived=False, changeable=True)

    def __init__(self, *, body=None, locale=None, **kwargs):

        super().__init__(**kwargs)

        if body is not None:
            self.body = body

        if locale is not None:
            self.locale = locale


class Conjugation(Relationship):
    """<p><code>Conjugation</code> is a <code>Relationship</code> between two types in which the <code>conjugatedType</code> inherits all the <code>Features</code> of the <code>originalType</code>, but with all <code>input</code> and <code>output</code> <code>Features</code> reversed. That is, any <code>Features</code> with a <code>direction</code> <em>in</em> relative to the <code>originalType</code> are considered to have an effective <code>direction</code> of <em>out</em> relative to the <code>conjugatedType</code> and, similarly, <code>Features</code> with <code>direction</code> <em>out</em> in the <code>originalType</code> are considered to have an effective <code>direction</code> of <em>in</em> in the <code>conjugatedType</code>. <code>Features</code> with <code>direction</code> <em>inout</em>, or with no <code>direction</code>, in the <code>originalType</code>, are inherited without change.</p>

<p>A <code>Type</code> may participate as a <code>conjugatedType</code> in at most one <code>Conjugation</code> relationship, and such a <code>Type</code> may not also be the <code>specific</code> <code>Type</code> in any <code>Specialization</code> relationship.</p>
"""
    conjugatedType = EReference(ordered=False, unique=True, containment=False, derived=False)
    originalType = EReference(ordered=False, unique=True, containment=False, derived=False)
    _owningType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='owningType', transient=True)

    @property
    def owningType(self):
        raise NotImplementedError('Missing implementation for owningType')

    @owningType.setter
    def owningType(self, value):
        raise NotImplementedError('Missing implementation for owningType')

    def __init__(self, *, conjugatedType=None, originalType=None, owningType=None, **kwargs):

        super().__init__(**kwargs)

        if conjugatedType is not None:
            self.conjugatedType = conjugatedType

        if originalType is not None:
            self.originalType = originalType

        if owningType is not None:
            self.owningType = owningType


class Dependency(Relationship):
    """<p>A <code>Dependency</code> is a <code>Relationship</code> that indicates that one or more <code>client</code> <code>Elements</code> require one more <code>supplier</code> <code>Elements</code> for their complete specification. In general, this means that a change to one of the <code>supplier</code> <code>Elements</code> may necessitate a change to, or re-specification of, the <code>client</code> <code>Elements</code>.</p>

<p>Note that a <code>Dependency</code> is entirely a model-level <code>Relationship</code>, without instance-level semantics.</p>"""
    client = EReference(ordered=True, unique=True, containment=False, derived=False, upper=-1)
    supplier = EReference(ordered=True, unique=True, containment=False, derived=False, upper=-1)

    def __init__(self, *, client=None, supplier=None, **kwargs):

        super().__init__(**kwargs)

        if client:
            self.client.extend(client)

        if supplier:
            self.supplier.extend(supplier)


class Differencing(Relationship):
    """<p><code>Differencing</code> is a <code>Relationship</code> that makes its <code>differencingType</code> one of the <code>differencingTypes</code> of its <code>typeDifferenced</code>.</p>
"""
    differencingType = EReference(ordered=False, unique=True, containment=False, derived=False)
    _typeDifferenced = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='typeDifferenced', transient=True)

    @property
    def typeDifferenced(self):
        raise NotImplementedError('Missing implementation for typeDifferenced')

    @typeDifferenced.setter
    def typeDifferenced(self, value):
        raise NotImplementedError('Missing implementation for typeDifferenced')

    def __init__(self, *, differencingType=None, typeDifferenced=None, **kwargs):

        super().__init__(**kwargs)

        if differencingType is not None:
            self.differencingType = differencingType

        if typeDifferenced is not None:
            self.typeDifferenced = typeDifferenced


class Disjoining(Relationship):
    """<p>A <code>Disjoining</code> is a <code>Relationship</code> between <code>Types</code> asserted to have interpretations that are not shared (disjoint) between them, identified as <code>typeDisjoined</code> and <code>disjoiningType</code>. For example, a <code>Classifier</code> for mammals is disjoint from a <code>Classifier</code> for minerals, and a <code>Feature</code> for people&#39;s parents is disjoint from a <code>Feature</code> for their children.</p>
"""
    disjoiningType = EReference(ordered=False, unique=True, containment=False, derived=False)
    _owningType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='owningType', transient=True)
    typeDisjoined = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def owningType(self):
        raise NotImplementedError('Missing implementation for owningType')

    @owningType.setter
    def owningType(self, value):
        raise NotImplementedError('Missing implementation for owningType')

    def __init__(self, *, disjoiningType=None, owningType=None, typeDisjoined=None, **kwargs):

        super().__init__(**kwargs)

        if disjoiningType is not None:
            self.disjoiningType = disjoiningType

        if owningType is not None:
            self.owningType = owningType

        if typeDisjoined is not None:
            self.typeDisjoined = typeDisjoined


class FeatureChaining(Relationship):
    """<p><code>FeatureChaining</code> is a <code>Relationship</code> that makes its target <code>Feature</code> one of the <code>chainingFeatures</code> of its owning <code>Feature</code>.</p>"""
    chainingFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    _featureChained = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='featureChained', transient=True)

    @property
    def featureChained(self):
        raise NotImplementedError('Missing implementation for featureChained')

    @featureChained.setter
    def featureChained(self, value):
        raise NotImplementedError('Missing implementation for featureChained')

    def __init__(self, *, chainingFeature=None, featureChained=None, **kwargs):

        super().__init__(**kwargs)

        if chainingFeature is not None:
            self.chainingFeature = chainingFeature

        if featureChained is not None:
            self.featureChained = featureChained


class FeatureInverting(Relationship):
    """<p>A <code>FeatureInverting</code> is a <code>Relationship</code> between <code>Features</code> asserting that their interpretations (sequences) are the reverse of each other, identified as <code>featureInverted</code> and <code>invertingFeature</code>. For example, a <code>Feature</code> identifying each person&#39;s parents is the inverse of a <code>Feature</code> identifying each person&#39;s children. A person identified as a parent of another will identify that other as one of their children.</p>
"""
    featureInverted = EReference(ordered=False, unique=True, containment=False, derived=False)
    invertingFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    _owningFeature = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='owningFeature', transient=True)

    @property
    def owningFeature(self):
        raise NotImplementedError('Missing implementation for owningFeature')

    @owningFeature.setter
    def owningFeature(self, value):
        raise NotImplementedError('Missing implementation for owningFeature')

    def __init__(self, *, featureInverted=None, invertingFeature=None, owningFeature=None, **kwargs):

        super().__init__(**kwargs)

        if featureInverted is not None:
            self.featureInverted = featureInverted

        if invertingFeature is not None:
            self.invertingFeature = invertingFeature

        if owningFeature is not None:
            self.owningFeature = owningFeature


@abstract
class Import(Relationship):
    """<p>An <code>Import</code> is an <code>Relationship</code> between its <code>importOwningNamespace</code> and either a <code>Membership</code> (for a <code>MembershipImport</code>) or another <code>Namespace</code> (for a <code>NamespaceImport</code>), which determines a set of <code>Memberships</code> that become <code>importedMemberships</code> of the <code>importOwningNamespace</code>. If <code>isImportAll = false</code> (the default), then only public <code>Memberships</code> are considered &quot;visible&quot;. If <code>isImportAll = true</code>, then all <code>Memberships</code> are considered &quot;visible&quot;, regardless of their declared <code>visibility</code>. If <code>isRecursive = true</code>, then visible <code>Memberships</code> are also recursively imported from owned sub-<code>Namespaces</code>.</p>


importOwningNamespace.owner = null implies 
    visibility = VisibilityKind::private"""
    isImportAll = EAttribute(eType=EBoolean, unique=True, derived=False,
                             changeable=True, default_value=False)
    isRecursive = EAttribute(eType=EBoolean, unique=True, derived=False,
                             changeable=True, default_value=False)
    visibility = EAttribute(eType=VisibilityKind, unique=True, derived=False,
                            changeable=True, default_value=VisibilityKind.private)
    _importOwningNamespace = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='importOwningNamespace', transient=True)
    _importedElement = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='importedElement', transient=True)

    @property
    def importOwningNamespace(self):
        raise NotImplementedError('Missing implementation for importOwningNamespace')

    @importOwningNamespace.setter
    def importOwningNamespace(self, value):
        raise NotImplementedError('Missing implementation for importOwningNamespace')

    @property
    def importedElement(self):
        raise NotImplementedError('Missing implementation for importedElement')

    @importedElement.setter
    def importedElement(self, value):
        raise NotImplementedError('Missing implementation for importedElement')

    def __init__(self, *, importOwningNamespace=None, importedElement=None, isImportAll=None, isRecursive=None, visibility=None, **kwargs):

        super().__init__(**kwargs)

        if isImportAll is not None:
            self.isImportAll = isImportAll

        if isRecursive is not None:
            self.isRecursive = isRecursive

        if visibility is not None:
            self.visibility = visibility

        if importOwningNamespace is not None:
            self.importOwningNamespace = importOwningNamespace

        if importedElement is not None:
            self.importedElement = importedElement

    def importedMemberships(self, excluded=None):
        """<p>Returns Memberships that are to become <code>importedMemberships</code> of the <code>importOwningNamespace</code>. (The <code>excluded</code> parameter is used to handle the possibility of circular Import Relationships.)</p>
"""
        raise NotImplementedError('operation importedMemberships(...) not yet implemented')


class Intersecting(Relationship):
    """<p><code>Intersecting</code> is a <code>Relationship</code> that makes its <code>intersectingType</code> one of the <code>intersectingTypes</code> of its <code>typeIntersected</code>.</p>
"""
    intersectingType = EReference(ordered=False, unique=True, containment=False, derived=False)
    _typeIntersected = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='typeIntersected', transient=True)

    @property
    def typeIntersected(self):
        raise NotImplementedError('Missing implementation for typeIntersected')

    @typeIntersected.setter
    def typeIntersected(self, value):
        raise NotImplementedError('Missing implementation for typeIntersected')

    def __init__(self, *, intersectingType=None, typeIntersected=None, **kwargs):

        super().__init__(**kwargs)

        if intersectingType is not None:
            self.intersectingType = intersectingType

        if typeIntersected is not None:
            self.typeIntersected = typeIntersected


class Membership(Relationship):
    """<p>A <code>Membership</code> is a <code>Relationship</code> between a <code>Namespace</code> and an <code>Element</code> that indicates the <code>Element</code> is a <code>member</code> of (i.e., is contained in) the Namespace. Any <code>memberNames</code> specify how the <code>memberElement</code> is identified in the <code>Namespace</code> and the <code>visibility</code> specifies whether or not the <code>memberElement</code> is publicly visible from outside the <code>Namespace</code>.</p>

<p>If a <code>Membership</code> is an <code>OwningMembership</code>, then it owns its <code>memberElement</code>, which becomes an <code>ownedMember</code> of the <code>membershipOwningNamespace</code>. Otherwise, the <code>memberNames</code> of a <code>Membership</code> are effectively aliases within the <code>membershipOwningNamespace</code> for an <code>Element</code> with a separate <code>OwningMembership</code> in the same or a different <code>Namespace</code>.</p>

<p>&nbsp;</p>

memberElementId = memberElement.elementId"""
    _memberElementId = EAttribute(eType=EString, unique=True, derived=True,
                                  changeable=True, name='memberElementId', transient=True)
    memberName = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    memberShortName = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    visibility = EAttribute(eType=VisibilityKind, unique=True, derived=False,
                            changeable=True, default_value=VisibilityKind.public)
    memberElement = EReference(ordered=False, unique=True, containment=False, derived=False)
    _membershipOwningNamespace = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='membershipOwningNamespace', transient=True)

    @property
    def memberElementId(self):
        raise NotImplementedError('Missing implementation for memberElementId')

    @memberElementId.setter
    def memberElementId(self, value):
        raise NotImplementedError('Missing implementation for memberElementId')

    @property
    def membershipOwningNamespace(self):
        raise NotImplementedError('Missing implementation for membershipOwningNamespace')

    @membershipOwningNamespace.setter
    def membershipOwningNamespace(self, value):
        raise NotImplementedError('Missing implementation for membershipOwningNamespace')

    def __init__(self, *, memberElement=None, memberElementId=None, memberName=None, memberShortName=None, membershipOwningNamespace=None, visibility=None, **kwargs):

        super().__init__(**kwargs)

        if memberElementId is not None:
            self.memberElementId = memberElementId

        if memberName is not None:
            self.memberName = memberName

        if memberShortName is not None:
            self.memberShortName = memberShortName

        if visibility is not None:
            self.visibility = visibility

        if memberElement is not None:
            self.memberElement = memberElement

        if membershipOwningNamespace is not None:
            self.membershipOwningNamespace = membershipOwningNamespace

    def isDistinguishableFrom(self, other=None):
        """<p>Whether this <code>Membership</code> is distinguishable from a given <code>other</code> <code>Membership</code>. By default, this is true if this <code>Membership</code> has no <code>memberShortName</code> or <code>memberName</code>; or each of the <code>memberShortName</code> and <code>memberName</code> are different than both of those of the <code>other</code> <code>Membership</code>; or neither of the metaclasses of the <code>memberElement</code> of this <code>Membership</code> and the <code>memberElement</code> of the <code>other</code> <code>Membership</code> conform to the other. But this may be overridden in specializations of <code>Membership</code>.</p>

not (memberElement.oclKindOf(other.memberElement.oclType()) or
     other.memberElement.oclKindOf(memberElement.oclType())) or
(shortMemberName = null or
    (shortMemberName <> other.shortMemberName and
     shortMemberName <> other.memberName)) and
(memberName = null or
    (memberName <> other.shortMemberName and
     memberName <> other.memberName)))
"""
        raise NotImplementedError('operation isDistinguishableFrom(...) not yet implemented')


class DerivedFiltercondition(EDerivedCollection):
    pass


class Package(Namespace):
    """<p>A <code>Package</code> is a <code>Namespace</code> used to group <code>Elements</code>, without any instance-level semantics. It may have one or more model-level evaluable <code>filterCondition</code> <code>Expressions</code> used to filter its <code>importedMemberships</code>. Any imported <code>member</code> must meet all of the <code>filterConditions</code>.</p>
filterCondition = ownedMembership->
    selectByKind(ElementFilterMembership).condition"""
    filterCondition = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedFiltercondition)

    def __init__(self, *, filterCondition=None, **kwargs):

        super().__init__(**kwargs)

        if filterCondition:
            self.filterCondition.extend(filterCondition)

    def includeAsMember(self, element=None):
        """<p>Determine whether the given <code>element</code> meets all the <code>filterConditions</code>.</p>
let metadataFeatures: Sequence(AnnotatingElement) = 
    element.ownedAnnotation.annotatingElement->
        selectByKind(MetadataFeature) in
    self.filterCondition->forAll(cond | 
        metadataFeatures->exists(elem | 
            cond.checkCondition(elem)))"""
        raise NotImplementedError('operation includeAsMember(...) not yet implemented')


class Specialization(Relationship):
    """<p><code>Specialization</code> is a <code>Relationship</code> between two <code>Types</code> that requires all instances of the <code>specific</code> type to also be instances of the <code>general</code> Type (i.e., the set of instances of the <code>specific</code> Type is a <em>subset</em> of those of the <code>general</code> Type, which might be the same set).</p>

not specific.isConjugated"""
    general = EReference(ordered=False, unique=True, containment=False, derived=False)
    _owningType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='owningType', transient=True)
    specific = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def owningType(self):
        raise NotImplementedError('Missing implementation for owningType')

    @owningType.setter
    def owningType(self, value):
        raise NotImplementedError('Missing implementation for owningType')

    def __init__(self, *, general=None, owningType=None, specific=None, **kwargs):

        super().__init__(**kwargs)

        if general is not None:
            self.general = general

        if owningType is not None:
            self.owningType = owningType

        if specific is not None:
            self.specific = specific


class TextualRepresentation(AnnotatingElement):
    """<p>A <code>TextualRepresentation</code> is an <code>AnnotatingElement</code> whose <code>body</code> represents the <code>representedElement</code> in a given <code>language</code>. The <code>representedElement</code> must be the <code>owner</code> of the <code>TextualRepresentation</code>. The named <code>language</code> can be a natural language, in which case the <code>body</code> is an informal representation, or an artificial language, in which case the <code>body</code> is expected to be a formal, machine-parsable representation.</p>

<p>If the named <code>language</code> of a <code>TextualRepresentation</code> is machine-parsable, then the <code>body</code> text should be legal input text as defined for that <code>language</code>. The interpretation of the named language string shall be case insensitive. The following <code>language</code> names are defined to correspond to the given standard languages:</p>

<table border="1" cellpadding="1" cellspacing="1" width="498">
        <thead>
        </thead>
        <tbody>
                <tr>
                        <td style="text-align: center; width: 154px;"><code>kerml</code></td>
                        <td style="width: 332px;">Kernel Modeling Language</td>
                </tr>
                <tr>
                        <td style="text-align: center; width: 154px;"><code>ocl</code></td>
                        <td style="width: 332px;">Object Constraint Language</td>
                </tr>
                <tr>
                        <td style="text-align: center; width: 154px;"><code>alf</code></td>
                        <td style="width: 332px;">Action Language for fUML</td>
                </tr>
        </tbody>
</table>

<p>Other specifications may define specific <code>language</code> strings, other than those shown above, to be used to indicate the use of languages from those specifications in KerML <code>TextualRepresentation</code>.</p>

<p>If the <code>language</code> of a <code>TextualRepresentation</code> is &quot;<code>kerml</code>&quot;, then the <code>body</code> text shall be a legal representation of the <code>representedElement</code> in the KerML textual concrete syntax. A conforming tool can use such a <code>TextualRepresentation</code> <code>Annotation</code> to record the original KerML concrete syntax text from which an <code>Element</code> was parsed. In this case, it is a tool responsibility to ensure that the <code>body</code> of the <code>TextualRepresentation</code> remains correct (or the Annotation is removed) if the annotated <code>Element</code> changes other than by re-parsing the <code>body</code> text.</p>

<p>An <code>Element</code> with a <code>TextualRepresentation</code> in a language other than KerML is essentially a semantically &quot;opaque&quot; <code>Element</code> specified in the other language. However, a conforming KerML tool may interpret such an element consistently with the specification of the named language.</p>
"""
    body = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    language = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    _representedElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='representedElement', transient=True)

    @property
    def representedElement(self):
        raise NotImplementedError('Missing implementation for representedElement')

    @representedElement.setter
    def representedElement(self, value):
        raise NotImplementedError('Missing implementation for representedElement')

    def __init__(self, *, body=None, language=None, representedElement=None, **kwargs):

        super().__init__(**kwargs)

        if body is not None:
            self.body = body

        if language is not None:
            self.language = language

        if representedElement is not None:
            self.representedElement = representedElement


class DerivedDifferencingtype(EDerivedCollection):
    pass


class DerivedDirectedfeature(EDerivedCollection):
    pass


class DerivedEndfeature(EDerivedCollection):
    pass


class DerivedFeature(EDerivedCollection):
    pass


class DerivedFeaturemembership(EDerivedCollection):
    pass


class DerivedInheritedfeature(EDerivedCollection):
    pass


class DerivedInheritedmembership(EDerivedCollection):
    pass


class DerivedInput(EDerivedCollection):
    pass


class DerivedIntersectingtype(EDerivedCollection):
    pass


class DerivedOutput(EDerivedCollection):
    pass


class DerivedOwneddifferencing(EDerivedCollection):
    pass


class DerivedOwneddisjoining(EDerivedCollection):
    pass


class DerivedOwnedendfeature(EDerivedCollection):
    pass


class DerivedOwnedfeature(EDerivedCollection):
    pass


class DerivedOwnedfeaturemembership(EDerivedCollection):
    pass


class DerivedOwnedintersecting(EDerivedCollection):
    pass


class DerivedOwnedspecialization(EDerivedCollection):
    pass


class DerivedOwnedunioning(EDerivedCollection):
    pass


class DerivedUnioningtype(EDerivedCollection):
    pass


class Type(Namespace):
    """<p>A <code>Type</code> is a <code>Namespace</code> that is the most general kind of <code>Element</code> supporting the semantics of classification. A <code>Type</code> may be a <code>Classifier</code> or a <code>Feature</code>, defining conditions on what is classified by the <code>Type</code> (see also the description of <code>isSufficient</code>).</p>

ownedSpecialization = ownedRelationship->selectByKind(Specialization)->
    select(s | s.special = self)

multiplicity = 
    let ownedMultiplicities: Sequence(Multiplicity) =
        ownedMember->selectByKind(Multiplicity) in
    if ownedMultiplicities->isEmpty() then null
    else ownedMultiplicities->first()
    endif
ownedFeatureMembership = ownedRelationship->selectByKind(FeatureMembership)
ownedConjugator =
    let ownedConjugators: Sequence(Conjugator) = 
        ownedRelationship->selectByKind(Conjugation) in
    if ownedConjugators->isEmpty() then null 
    else ownedConjugators->at(1) endif
output = feature->select(f | 
    let direction: FeatureDirectionKind = directionOf(f) in
    direction = FeatureDirectionKind::out or
    direction = FeatureDirectionKind::inout)
input = feature->select(f | 
    let direction: FeatureDirectionKind = directionOf(f) in
    direction = FeatureDirectionKind::_'in' or
    direction = FeatureDirectionKind::inout)
inheritedMembership = inheritedMemberships(Set{}, Set{}, false)
specializesFromLibrary('Base::Anything')
directedFeature = feature->select(f | directionOf(f) <> null)
feature = featureMembership.ownedMemberFeature
featureMembership = ownedFeatureMembership->union(
    inheritedMembership->selectByKind(FeatureMembership))
ownedFeature = ownedFeatureMembership.ownedMemberFeature
differencingType = ownedDifferencing.differencingType
intersectingType->excludes(self)
differencingType->excludes(self)
unioningType = ownedUnioning.unioningType
unioningType->excludes(self)
intersectingType = ownedIntersecting.intersectingType
ownedRelationship->selectByKind(Conjugation)->size() <= 1
ownedMember->selectByKind(Multiplicity)->size() <= 1
endFeature = feature->select(isEnd)
ownedDisjoining =
    ownedRelationship->selectByKind(Disjoining)
ownedUnioning =
    ownedRelationship->selectByKind(Unioning)
ownedRelationship->selectByKind(Intersecting)
ownedDifferencing =
    ownedRelationship->selectByKind(Differencing)
ownedEndFeature = ownedFeature->select(isEnd)
inheritedFeature = inheritedMemberships->
    selectByKind(FeatureMembership).memberFeature
ownedUnioning->size() <> 1
ownedIntersecting->size() <> 1
ownedDifferencing->size() <> 1"""
    isAbstract = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)
    _isConjugated = EAttribute(eType=EBoolean, unique=True, derived=True,
                               changeable=True, name='isConjugated', transient=True)
    isSufficient = EAttribute(eType=EBoolean, unique=True, derived=False,
                              changeable=True, default_value=False)
    differencingType = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedDifferencingtype)
    directedFeature = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedDirectedfeature)
    endFeature = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedEndfeature)
    feature = EReference(ordered=True, unique=True, containment=False,
                         derived=True, upper=-1, transient=True, derived_class=DerivedFeature)
    featureMembership = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedFeaturemembership)
    inheritedFeature = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedInheritedfeature)
    inheritedMembership = EReference(ordered=True, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedInheritedmembership)
    input = EReference(ordered=True, unique=True, containment=False, derived=True,
                       upper=-1, transient=True, derived_class=DerivedInput)
    intersectingType = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedIntersectingtype)
    _multiplicity = EReference(ordered=False, unique=True, containment=False,
                               derived=True, name='multiplicity', transient=True)
    output = EReference(ordered=True, unique=True, containment=False, derived=True,
                        upper=-1, transient=True, derived_class=DerivedOutput)
    _ownedConjugator = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='ownedConjugator', transient=True)
    ownedDifferencing = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedOwneddifferencing)
    ownedDisjoining = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwneddisjoining)
    ownedEndFeature = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedendfeature)
    ownedFeature = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedOwnedfeature)
    ownedFeatureMembership = EReference(ordered=True, unique=True, containment=False,
                                        derived=True, upper=-1, transient=True, derived_class=DerivedOwnedfeaturemembership)
    ownedIntersecting = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedOwnedintersecting)
    ownedSpecialization = EReference(ordered=True, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedOwnedspecialization)
    ownedUnioning = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedOwnedunioning)
    unioningType = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedUnioningtype)

    @property
    def isConjugated(self):
        raise NotImplementedError('Missing implementation for isConjugated')

    @isConjugated.setter
    def isConjugated(self, value):
        raise NotImplementedError('Missing implementation for isConjugated')

    @property
    def multiplicity(self):
        raise NotImplementedError('Missing implementation for multiplicity')

    @multiplicity.setter
    def multiplicity(self, value):
        raise NotImplementedError('Missing implementation for multiplicity')

    @property
    def ownedConjugator(self):
        raise NotImplementedError('Missing implementation for ownedConjugator')

    @ownedConjugator.setter
    def ownedConjugator(self, value):
        raise NotImplementedError('Missing implementation for ownedConjugator')

    def __init__(self, *, differencingType=None, directedFeature=None, endFeature=None, feature=None, featureMembership=None, inheritedFeature=None, inheritedMembership=None, input=None, intersectingType=None, isAbstract=None, isConjugated=None, isSufficient=None, multiplicity=None, output=None, ownedConjugator=None, ownedDifferencing=None, ownedDisjoining=None, ownedEndFeature=None, ownedFeature=None, ownedFeatureMembership=None, ownedIntersecting=None, ownedSpecialization=None, ownedUnioning=None, unioningType=None, **kwargs):

        super().__init__(**kwargs)

        if isAbstract is not None:
            self.isAbstract = isAbstract

        if isConjugated is not None:
            self.isConjugated = isConjugated

        if isSufficient is not None:
            self.isSufficient = isSufficient

        if differencingType:
            self.differencingType.extend(differencingType)

        if directedFeature:
            self.directedFeature.extend(directedFeature)

        if endFeature:
            self.endFeature.extend(endFeature)

        if feature:
            self.feature.extend(feature)

        if featureMembership:
            self.featureMembership.extend(featureMembership)

        if inheritedFeature:
            self.inheritedFeature.extend(inheritedFeature)

        if inheritedMembership:
            self.inheritedMembership.extend(inheritedMembership)

        if input:
            self.input.extend(input)

        if intersectingType:
            self.intersectingType.extend(intersectingType)

        if multiplicity is not None:
            self.multiplicity = multiplicity

        if output:
            self.output.extend(output)

        if ownedConjugator is not None:
            self.ownedConjugator = ownedConjugator

        if ownedDifferencing:
            self.ownedDifferencing.extend(ownedDifferencing)

        if ownedDisjoining:
            self.ownedDisjoining.extend(ownedDisjoining)

        if ownedEndFeature:
            self.ownedEndFeature.extend(ownedEndFeature)

        if ownedFeature:
            self.ownedFeature.extend(ownedFeature)

        if ownedFeatureMembership:
            self.ownedFeatureMembership.extend(ownedFeatureMembership)

        if ownedIntersecting:
            self.ownedIntersecting.extend(ownedIntersecting)

        if ownedSpecialization:
            self.ownedSpecialization.extend(ownedSpecialization)

        if ownedUnioning:
            self.ownedUnioning.extend(ownedUnioning)

        if unioningType:
            self.unioningType.extend(unioningType)

    def allRedefinedFeaturesOf(self, membership=None):
        """<p>If the <code>memberElement</code> of the given <code>membership</code> is a <code>Feature</code>, then return all <code>Features</code> directly or indirectly redefined by the <code>memberElement</code>.</p>
if not membership.memberElement.oclIsType(Feature) then Set{} 
else membership.memberElement.oclAsType(Feature).allRedefinedFeatures()
endif"""
        raise NotImplementedError('operation allRedefinedFeaturesOf(...) not yet implemented')

    def allSupertypes(self):
        """<p>Return this <code>Type</code> and all <code>Types</code> that are directly or transitively supertypes of this <code>Type</code> (as determined by the <code>supertypes</code> operation with <code>excludeImplied = false</code>).</p>

OrderedSet{self}->closure(supertypes(false))"""
        raise NotImplementedError('operation allSupertypes(...) not yet implemented')

    def directionOf(self, feature=None):
        """<p>If the given <code>feature</code> is a <code>feature</code> of this <code>Type</code>, then return its direction relative to this <code>Type</code>, taking conjugation into account.</p>

directionOfExcluding(f, Set{})"""
        raise NotImplementedError('operation directionOf(...) not yet implemented')

    def directionOfExcluding(self, feature=None, excluded=None):
        """<p>Return the direction of the given <code>feature</code> relative to this <code>Type</code>, excluding a given set of <code>Types</code> from the search of supertypes of this <code>Type</code>.</p>
let excludedSelf : Set(Type) = excluded->including(self) in 
if feature.owningType = self then feature.direction
else
    let directions : Sequence(FeatureDirectionKind) =
        supertypes(false)->excluding(excludedSelf).
        directionOfExcluding(feature, excludedSelf)->
        select(d | d <> null) in
    if directions->isEmpty() then null
 else
    let direction : FeatureDirectionKind = directions->first() in
    if not isConjugated then direction
    else if direction = FeatureDirectionKind::_'in' then FeatureDirectionKind::out
    else if direction = FeatureDirectionKind::out then FeatureDirectionKind::_'in'
    else direction
    endif endif endif   endif
endif"""
        raise NotImplementedError('operation directionOfExcluding(...) not yet implemented')

    def inheritableMemberships(self, excludedNamespaces=None, excludedTypes=None, excludeImplied=None):
        """<p>Return all the non-<code>private</code> <code>Memberships</code> of all the supertypes of this <code>Type</code>, excluding any supertypes that are this <code>Type</code> or are in the given set of <code>excludedTypes</code>. If <code>excludeImplied = true</code>, then also transitively exclude any supertypes from implied <code>Specializations</code>.</p>
let excludingSelf : Set(Type) = excludedType->including(self) in
supertypes(excludeImplied)->reject(t | excludingSelf->includes(t)).
    nonPrivateMemberships(excludedNamespaces, excludingSelf, excludeImplied)
"""
        raise NotImplementedError('operation inheritableMemberships(...) not yet implemented')

    def inheritedMemberships(self, excludedNamespaces=None, excludedTypes=None, excludeImplied=None):
        """<p>Return the <code>Memberships</code> inheritable from supertypes of this <code>Type</code> with redefined <code>Features</code> removed. When computing inheritable <code>Memberships</code>, exclude <code>Imports</code> of <code>excludedNamespaces</code>, <code>Specializations</code> of <code>excludedTypes</code>, and, if <code>excludeImplied = true</code>, all implied <code>Specializations</code>.</p>

removeRedefinedFeatures(
    inheritableMemberships(excludedNamespaces, excludedTypes, excludeImplied))"""
        raise NotImplementedError('operation inheritedMemberships(...) not yet implemented')

    def isCompatibleWith(self, otherType=None):
        """<p>By default, this <code>Type</code> is compatible with an <code>otherType</code> if it directly or indirectly specializes the <code>otherType</code>.</p>
specializes(otherType)"""
        raise NotImplementedError('operation isCompatibleWith(...) not yet implemented')

    def multiplicities(self):
        """<p>Return the owned or inherited <code>Multiplicities</code> for this <code>Type<./code>.</p>
if multiplicity <> null then OrderedSet{multiplicity}
else 
    ownedSpecialization.general->closure(t |
        if t.multiplicity <> null then OrderedSet{}
        else ownedSpecialization.general
    )->select(multiplicity <> null).multiplicity->asOrderedSet()
endif"""
        raise NotImplementedError('operation multiplicities(...) not yet implemented')

    def nonPrivateMemberships(self, excludedNamespaces=None, excludedTypes=None, excludeImplied=None):
        """<p>Return the <code>public</code>, <code>protected</code> and inherited <code>Memberships</code> of this <code>Type</code>. When computing imported <code>Memberships</code>, exclude the given set of <code>excludedNamespaces</code>. When computing inherited <code>Memberships</code>, exclude <code>Types</code> in the given set of <code>excludedTypes</code>. If <code>excludeImplied = true</code>, then also exclude any supertypes from implied <code>Specializations</code>.</p>
let publicMemberships : OrderedSet(Membership) = 
    membershipsOfVisibility(VisibilityKind::public, excludedNamespaces) in
let protectedMemberships : OrderedSet(Membership) = 
    membershipsOfVisibility(VisibilityKind::protected, excludedNamespaces) in
let inheritedMemberships : OrderedSet(Membership) =
    inheritedMemberships(excludedNamespaces, excludedTypes, excludeImplied) in
publicMemberships->
    union(protectedMemberships)->
    union(inheritedMemberships)"""
        raise NotImplementedError('operation nonPrivateMemberships(...) not yet implemented')

    def removeRedefinedFeatures(self, memberships=None):
        """<p>Return a subset of <code>memberships</code>, removing those <code>Memberships</code> whose <code>memberElements</code> are <code>Features</code> and for which either of the following two conditions holds:</p>

<ol>
        <li>The <code>memberElement</code> of the <code>Membership</code> is included in redefined <code>Features</code> of another <code>Membership</code> in <code>memberships</code>.</li>
        <li>One of the redefined <code>Features</code> of the <code>Membership</code> is a directly <code>redefinedFeature</code> of an <code>ownedFeature</code> of this <code>Type</code>.</li>
</ol>

<p>For this purpose, the redefined <code>Features</code> of a <code>Membership</code> whose <code>memberElement</code> is a <code>Feature</code> includes the <code>memberElement</code> and all <code>Features</code> directly or indirectly redefined by the <code>memberElement</code>.</p>
let reducedMemberships : Sequence(Membership) =
    memberships->reject(mem1 |
        memberships->excluding(mem1)->
            exists(mem2 | allRedefinedFeaturesOf(mem2)->
                includes(mem1.memberElement))) in
let redefinedFeatures : Set(Feature) = 
    ownedFeature.redefinition.redefinedFeature->asSet() in
reducedMemberships->reject(mem | allRedefinedFeaturesOf(mem)->
    exists(feature | redefinedFeatures->includes(feature)))"""
        raise NotImplementedError('operation removeRedefinedFeatures(...) not yet implemented')

    def specializes(self, supertype=None):
        """<p>Check whether this <code>Type</code> is a direct or indirect specialization of the given <code>supertype<code>.</p>
if isConjugated then 
    ownedConjugator.originalType.specializes(supertype)
else
    allSupertypes()->includes(supertype)
endif"""
        raise NotImplementedError('operation specializes(...) not yet implemented')

    def specializesFromLibrary(self, libraryTypeName=None):
        """<p>Check whether this <code>Type</code> is a direct or indirect specialization of the named library <code>Type</code>. <code>libraryTypeName</code> must conform to the syntax of a KerML qualified name and must resolve to a <code>Type</code> in global scope.</p>

let mem : Membership = resolveGlobal(libraryTypeName) in
mem <> null and mem.memberElement.oclIsKindOf(Type) and
specializes(mem.memberElement.oclAsType(Type))"""
        raise NotImplementedError('operation specializesFromLibrary(...) not yet implemented')

    def supertypes(self, excludeImplied=None):
        """<p>If this <code>Type</code> is conjugated, then return just the <code>originalType</code> of the <code>Conjugation</code>. Otherwise, return the <code>general</code> <code>Types</code> from all <code>ownedSpecializations</code> of this type, if <code>excludeImplied = false</code>, or all non-implied <code>ownedSpecializations</code>, if <code>excludeImplied = true</code>.</p>
if isConjugated then Sequence{conjugator.originalType}
else if not excludeImplied then ownedSpecialization.general
else ownedSpecialization->reject(isImplied).general
endif
endif"""
        raise NotImplementedError('operation supertypes(...) not yet implemented')


class TypeFeaturing(Relationship):
    """<p>A <code>TypeFeaturing</code> is a <code>Featuring</code> <code>Relationship</code> in which the <code>featureOfType</code> is the <code>source</code> and the <code>featuringType</code> is the <code>target</code>.</p>"""
    featureOfType = EReference(ordered=False, unique=True, containment=False, derived=False)
    featuringType = EReference(ordered=False, unique=True, containment=False, derived=False)
    _owningFeatureOfType = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='owningFeatureOfType', transient=True)

    @property
    def owningFeatureOfType(self):
        raise NotImplementedError('Missing implementation for owningFeatureOfType')

    @owningFeatureOfType.setter
    def owningFeatureOfType(self, value):
        raise NotImplementedError('Missing implementation for owningFeatureOfType')

    def __init__(self, *, featureOfType=None, featuringType=None, owningFeatureOfType=None, **kwargs):

        super().__init__(**kwargs)

        if featureOfType is not None:
            self.featureOfType = featureOfType

        if featuringType is not None:
            self.featuringType = featuringType

        if owningFeatureOfType is not None:
            self.owningFeatureOfType = owningFeatureOfType


class Unioning(Relationship):
    """<p><code>Unioning</code> is a <code>Relationship</code> that makes its <code>unioningType</code> one of the <code>unioningTypes</code> of its <code>typeUnioned</code>.</p>
"""
    _typeUnioned = EReference(ordered=False, unique=True, containment=False,
                              derived=True, name='typeUnioned', transient=True)
    unioningType = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def typeUnioned(self):
        raise NotImplementedError('Missing implementation for typeUnioned')

    @typeUnioned.setter
    def typeUnioned(self, value):
        raise NotImplementedError('Missing implementation for typeUnioned')

    def __init__(self, *, typeUnioned=None, unioningType=None, **kwargs):

        super().__init__(**kwargs)

        if typeUnioned is not None:
            self.typeUnioned = typeUnioned

        if unioningType is not None:
            self.unioningType = unioningType


class DerivedOwnedsubclassification(EDerivedCollection):
    pass


class Classifier(Type):
    """<p>A <code>Classifier</code> is a <code>Type</code> that classifies:</p>

<ul>
        <li>Things (in the universe) regardless of how <code>Features</code> relate them. (These are interpreted semantically as sequences of exactly one thing.)</li>
        <li>How the above things are related by <code>Features.</code> (These are interpreted semantically as sequences of multiple things, such that the last thing in the sequence is also classified by the <code>Classifier</code>. Note that this means that a <code>Classifier</code> modeled as specializing a <code>Feature</code> cannot classify anything.)</li>
</ul>


ownedSubclassification = 
    ownedSpecialization->selectByKind(Subclassification)
multiplicity <> null implies multiplicity.featuringType->isEmpty()"""
    ownedSubclassification = EReference(ordered=False, unique=True, containment=False,
                                        derived=True, upper=-1, transient=True, derived_class=DerivedOwnedsubclassification)

    def __init__(self, *, ownedSubclassification=None, **kwargs):

        super().__init__(**kwargs)

        if ownedSubclassification:
            self.ownedSubclassification.extend(ownedSubclassification)


class Documentation(Comment):
    """<p><code>Documentation</code> is a <code>Comment</code> that specifically documents a <code>documentedElement</code>, which must be its <code>owner</code>.</p>
"""
    _documentedElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='documentedElement', transient=True)

    @property
    def documentedElement(self):
        raise NotImplementedError('Missing implementation for documentedElement')

    @documentedElement.setter
    def documentedElement(self, value):
        raise NotImplementedError('Missing implementation for documentedElement')

    def __init__(self, *, documentedElement=None, **kwargs):

        super().__init__(**kwargs)

        if documentedElement is not None:
            self.documentedElement = documentedElement


@abstract
class Expose(Import):
    """<p>An <code>Expose</code> is an <code>Import</code> of <code>Memberships</code> into a <code>ViewUsage</code> that provide the <code>Elements</code> to be included in a view. Visibility is always ignored for an <code>Expose</code> (i.e., <code>isImportAll = true</code>).</p>
isImportAll
importOwningNamespace.oclIsType(ViewUsage)
visibility = VisibilityKind::protected"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedChainingfeature(EDerivedCollection):
    pass


class DerivedFeaturingtype(EDerivedCollection):
    pass


class DerivedOwnedfeaturechaining(EDerivedCollection):
    pass


class DerivedOwnedfeatureinverting(EDerivedCollection):
    pass


class DerivedOwnedredefinition(EDerivedCollection):
    pass


class DerivedOwnedsubsetting(EDerivedCollection):
    pass


class DerivedOwnedtypefeaturing(EDerivedCollection):
    pass


class DerivedOwnedtyping(EDerivedCollection):
    pass


class DerivedType(EDerivedCollection):
    pass


class Feature(Type):
    """<p>A <code>Feature</code> is a <code>Type</code> that classifies relations between multiple things (in the universe). The domain of the relation is the intersection of the <code>featuringTypes</code> of the <code>Feature</code>. (The domain of a <code>Feature</code> with no <code>featuringTyps</code> is implicitly the most general <code>Type</code> <em><code>Base::Anything</code></em> from the Kernel Semantic Library.) The co-domain of the relation is the intersection of the <code>types</code> of the <code>Feature</code>.

<p>In the simplest cases, the <code>featuringTypes</code> and <code>types</code> are <code>Classifiers</code> and the <code>Feature</code> relates two things, one from the domain and one from the range. Examples include cars paired with wheels, people paired with other people, and cars paired with numbers representing the car length.</p>

<p>Since <code>Features</code> are <code>Types</code>, their <code>featuringTypes</code> and <code>types</code> can be <code>Features</code>. In this case, the <code>Feature</code> effectively classifies relations between relations, which can be interpreted as the sequence of things related by the domain <code>Feature</code> concatenated with the sequence of things related by the co-domain <code>Feature</code>.</p>

<p>The <em>values</em> of a <code>Feature</code> for a given instance of its domain are all the instances of its co-domain that are related to that domain instance by the <code>Feature</code>. The values of a <code>Feature</code> with <code>chainingFeatures</code> are the same as values of the last <code>Feature</code> in the chain, which can be found by starting with values of the first <code>Feature</code>, then using those values as domain instances to obtain valus of the second <code>Feature</code>, and so on, to values of the last <code>Feature</code>.</p>

ownedRedefinition = ownedSubsetting->selectByKind(Redefinition)
ownedTypeFeaturing = ownedRelationship->selectByKind(TypeFeaturing)->
    select(tf | tf.featureOfType = self)
ownedSubsetting = ownedSpecialization->selectByKind(Subsetting)
ownedTyping = ownedGeneralization->selectByKind(FeatureTyping)
type = 
    let types : OrderedSet(Types) = OrderedSet{self}->
        -- Note: The closure operation automatically handles circular relationships.
        closure(typingFeatures()).typing.type->asOrderedSet() in
    types->reject(t1 | types->exist(t2 | t2 <> t1 and t2.specializes(t1)))
multiplicity <> null implies multiplicity.featuringType = featuringType 
specializesFromLibrary('Base::things')
chainingFeature->excludes(self)
ownedFeatureChaining = ownedRelationship->selectByKind(FeatureChaining)
chainingFeature = ownedFeatureChaining.chainingFeature
chainingFeature->size() <> 1
isEnd and owningType <> null implies
    let i : Integer = 
        owningType.ownedEndFeature->indexOf(self) in
    owningType.ownedSpecialization.general->
        forAll(supertype |
             supertype.endFeature->size() >= i implies
                redefines(supertype.endFeature->at(i))
direction = null and
ownedSpecializations->forAll(isImplied) implies
    ownedMembership->
        selectByKind(FeatureValue)->
        forAll(fv | specializes(fv.value.result))
isEnd and owningType <> null and
(owningType.oclIsKindOf(Association) or
 owningType.oclIsKindOf(Connector)) implies
    specializesFromLibrary('Links::Link::participant')
isComposite and
ownedTyping.type->includes(oclIsKindOf(Structure)) and
owningType <> null and
(owningType.oclIsKindOf(Structure) or
 owningType.type->includes(oclIsKindOf(Structure))) implies
    specializesFromLibrary('Occurrence::Occurrence::suboccurrences')
ownedTyping.type->exists(selectByKind(Class)) implies
    specializesFromLibrary('Occurrences::occurrences')
isComposite and
ownedTyping.type->includes(oclIsKindOf(Class)) and
owningType <> null and
(owningType.oclIsKindOf(Class) or
 owningType.oclIsKindOf(Feature) and
    owningType.oclAsType(Feature).type->
        exists(oclIsKindOf(Class))) implies
    specializesFromLibrary('Occurrence::Occurrence::suboccurrences')
ownedTyping.type->exists(selectByKind(DataType)) implies
    specializesFromLibrary('Base::dataValues')
owningType <> null and
owningType.oclIsKindOf(FlowEnd) and
owningType.ownedFeature->at(1) = self implies
    let flowType : Type = owningType.owningType in
    flowType <> null implies
        let i : Integer = 
            flowType.ownedFeature.indexOf(owningType) in
        (i = 1 implies 
            redefinesFromLibrary('Transfers::Transfer::source::sourceOutput')) and
        (i = 2 implies
            redefinesFromLibrary('Transfers::Transfer::target::targetInput'))

owningType <> null and
(owningType.oclIsKindOf(Behavior) or
 owningType.oclIsKindOf(Step) and
    (owningType.oclIsKindOf(InvocationExpression) implies
        not ownedRedefinition->exists(not isImplied)))
implies
    let ownerParameters : Sequence(Feature) =
        owningType.ownedFeature->select(direction <> null)->
            reject(owningFeatureMembership.
                oclIsKindOf(ReturnParameterMembership)) in
    ownerParameters->includes(self) implies
        let i : Integer = ownerParameters.indexof(self) in
        owningType.ownedSpecialization.general->
            forAll(supertype |
                supertype.oclIsKindOf(Behavior) or 
                    supertype.oclIsKindOf(Step) 
                implies
                    let ownedParameters : Sequence(Feature) =
                        supertype.ownedFeature->select(direction <> null)->
                            reject(owningFeatureMembership.
                                oclIsKindOf(ReturnParameterMembership)) in
                    ownedParameters->size() >= i implies
                        redefines(ownedParameters->at(i)))
ownedTyping.type->exists(selectByKind(Structure)) implies
    specializesFromLibrary('Objects::objects')
owningType <> null and
(owningType.oclIsKindOf(Function) and
    self = owningType.oclAsType(Function).result or
 owningType.oclIsKindOf(Expression) and
    self = owningType.oclAsType(Expression).result) implies
    owningType.ownedSpecialization.general->
        select(oclIsKindOf(Function) or oclIsKindOf(Expression))->
        forAll(supertype |
            redefines(
                if superType.oclIsKindOf(Function) then
                    superType.oclAsType(Function).result
                else
                    superType.oclAsType(Expression).result
                endif)
ownedFeatureInverting = ownedRelationship->selectByKind(FeatureInverting)->
    select(fi | fi.featureInverted = self)
featuringType =
    let featuringTypes : OrderedSet(Type) = 
        typeFeaturing.type->asOrderedSet() in
    if chainingFeature->isEmpty() then featuringTypes
    else
        featuringTypes->
            union(chainingFeature->first().featuringType)->
            asOrderedSet()
    endif
ownedReferenceSubsetting =
    let referenceSubsettings : OrderedSet(ReferenceSubsetting) =
        ownedSubsetting->selectByKind(ReferenceSubsetting) in
    if referenceSubsettings->isEmpty() then null
    else referenceSubsettings->first() endif
ownedSubsetting->selectByKind(ReferenceSubsetting)->size() <= 1
Sequence{2..chainingFeature->size()}->forAll(i |
    chainingFeature->at(i).isFeaturedWithin(chainingFeature->at(i-1)))

isPortion and
ownedTyping.type->includes(oclIsKindOf(Class)) and
owningType <> null and
(owningType.oclIsKindOf(Class) or
 owningType.oclIsKindOf(Feature) and
    owningType.oclAsType(Feature).type->
        exists(oclIsKindOf(Class))) implies
    specializesFromLibrary('Occurrence::Occurrence::portions')
featureTarget = if chainingFeature->isEmpty() then self else chainingFeature->last() endif
ownedCrossSubsetting =
    let crossSubsettings: Sequence(CrossSubsetting) = 
        ownedSubsetting->selectByKind(CrossSubsetting) in
    if crossSubsettings->isEmpty() then null
    else crossSubsettings->first()
    endif
isEnd implies 
    multiplicities().allSuperTypes()->flatten()->
    selectByKind(MultiplicityRange)->exists(hasBounds(1,1))
crossFeature <> null implies
    crossFeature.type->asSet() = type->asSet()
ownedSubsetting->selectByKind(CrossSubsetting)->size() <= 1
crossFeature =
    if ownedCrossSubsetting = null then null
    else 
        let chainingFeatures: Sequence(Feature) = 
            ownedCrossSubsetting.crossedFeature.chainingFeature in
        if chainingFeatures->size() < 2 then null
        else chainingFeatures->at(2)
    endif
isOwnedCrossFeature() implies
    owner.oclAsType(Feature).type->forAll(t | self.specializes(t))
isOwnedCrossFeature() implies
    ownedSubsetting.subsettedFeature->includesAll(
        owner.oclAsType(Feature).ownedRedefinition.redefinedFeature->
            select(crossFeature <> null).crossFeature)
crossFeature <> null implies
    ownedRedefinition.redefinedFeature.crossFeature->
            forAll(f | f <> null implies crossFeature.specializes(f))
ownedCrossFeature() <> null implies
    crossFeature = ownedCrossFeature()
isOwnedCrossFeature() implies
    let otherEnds : OrderedSet(Feature) = 
        owner.oclAsType(Feature).owningType.endFeature->excluding(self) in
    if (otherEnds->size() = 1) then
        featuringType = otherEnds->first().type
    else
        featuringType->size() = 1 and
        featuringType->first().isCartesianProduct() and
        featuringType->first().asCartesianProduct() = otherEnds.type and
        featuringType->first().allSupertypes()->includesAll(
            owner.oclAsType(Feature).ownedRedefinition.redefinedFeature->
               select(crossFeature() <> null).crossFeature().featuringType)      
    endif
isPortion implies not isVariable
isEnd implied direction = null
owningFeatureMembership <> null implies
    featuringTypes->exists(t | isFeaturingType(t))
isConstant implies isVariable
isVariable implies
    owningType <> null and 
    owningType.specializes('Occurrences::Occurrence')
isEnd implies not (isDerived or isAbstract or isComposite or isPortion)
isEnd and isVariable implies isConstant"""
    direction = EAttribute(eType=FeatureDirectionKind, unique=True, derived=False, changeable=True)
    isComposite = EAttribute(eType=EBoolean, unique=True, derived=False,
                             changeable=True, default_value=False)
    isConstant = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)
    isDerived = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    isEnd = EAttribute(eType=EBoolean, unique=True, derived=False,
                       changeable=True, default_value=False)
    isOrdered = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    isPortion = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    isUnique = EAttribute(eType=EBoolean, unique=True, derived=False,
                          changeable=True, default_value=True)
    isVariable = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)
    chainingFeature = EReference(ordered=True, unique=False, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedChainingfeature)
    _crossFeature = EReference(ordered=False, unique=True, containment=False,
                               derived=True, name='crossFeature', transient=True)
    _endOwningType = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='endOwningType', transient=True)
    _featureTarget = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='featureTarget', transient=True)
    featuringType = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedFeaturingtype)
    _ownedCrossSubsetting = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedCrossSubsetting', transient=True)
    ownedFeatureChaining = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedOwnedfeaturechaining)
    ownedFeatureInverting = EReference(ordered=False, unique=True, containment=False,
                                       derived=True, upper=-1, transient=True, derived_class=DerivedOwnedfeatureinverting)
    ownedRedefinition = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedOwnedredefinition)
    _ownedReferenceSubsetting = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedReferenceSubsetting', transient=True)
    ownedSubsetting = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedsubsetting)
    ownedTypeFeaturing = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedOwnedtypefeaturing)
    ownedTyping = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedOwnedtyping)
    _owningFeatureMembership = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='owningFeatureMembership', transient=True)
    _owningType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='owningType', transient=True)
    type = EReference(ordered=True, unique=True, containment=False, derived=True,
                      upper=-1, transient=True, derived_class=DerivedType)

    @property
    def crossFeature(self):
        raise NotImplementedError('Missing implementation for crossFeature')

    @crossFeature.setter
    def crossFeature(self, value):
        raise NotImplementedError('Missing implementation for crossFeature')

    @property
    def endOwningType(self):
        raise NotImplementedError('Missing implementation for endOwningType')

    @endOwningType.setter
    def endOwningType(self, value):
        raise NotImplementedError('Missing implementation for endOwningType')

    @property
    def featureTarget(self):
        raise NotImplementedError('Missing implementation for featureTarget')

    @featureTarget.setter
    def featureTarget(self, value):
        raise NotImplementedError('Missing implementation for featureTarget')

    @property
    def ownedCrossSubsetting(self):
        raise NotImplementedError('Missing implementation for ownedCrossSubsetting')

    @ownedCrossSubsetting.setter
    def ownedCrossSubsetting(self, value):
        raise NotImplementedError('Missing implementation for ownedCrossSubsetting')

    @property
    def ownedReferenceSubsetting(self):
        raise NotImplementedError('Missing implementation for ownedReferenceSubsetting')

    @ownedReferenceSubsetting.setter
    def ownedReferenceSubsetting(self, value):
        raise NotImplementedError('Missing implementation for ownedReferenceSubsetting')

    @property
    def owningFeatureMembership(self):
        raise NotImplementedError('Missing implementation for owningFeatureMembership')

    @owningFeatureMembership.setter
    def owningFeatureMembership(self, value):
        raise NotImplementedError('Missing implementation for owningFeatureMembership')

    @property
    def owningType(self):
        raise NotImplementedError('Missing implementation for owningType')

    @owningType.setter
    def owningType(self, value):
        raise NotImplementedError('Missing implementation for owningType')

    def __init__(self, *, chainingFeature=None, crossFeature=None, direction=None, endOwningType=None, featureTarget=None, featuringType=None, isComposite=None, isConstant=None, isDerived=None, isEnd=None, isOrdered=None, isPortion=None, isUnique=None, isVariable=None, ownedCrossSubsetting=None, ownedFeatureChaining=None, ownedFeatureInverting=None, ownedRedefinition=None, ownedReferenceSubsetting=None, ownedSubsetting=None, ownedTypeFeaturing=None, ownedTyping=None, owningFeatureMembership=None, owningType=None, type=None, **kwargs):

        super().__init__(**kwargs)

        if direction is not None:
            self.direction = direction

        if isComposite is not None:
            self.isComposite = isComposite

        if isConstant is not None:
            self.isConstant = isConstant

        if isDerived is not None:
            self.isDerived = isDerived

        if isEnd is not None:
            self.isEnd = isEnd

        if isOrdered is not None:
            self.isOrdered = isOrdered

        if isPortion is not None:
            self.isPortion = isPortion

        if isUnique is not None:
            self.isUnique = isUnique

        if isVariable is not None:
            self.isVariable = isVariable

        if chainingFeature:
            self.chainingFeature.extend(chainingFeature)

        if crossFeature is not None:
            self.crossFeature = crossFeature

        if endOwningType is not None:
            self.endOwningType = endOwningType

        if featureTarget is not None:
            self.featureTarget = featureTarget

        if featuringType:
            self.featuringType.extend(featuringType)

        if ownedCrossSubsetting is not None:
            self.ownedCrossSubsetting = ownedCrossSubsetting

        if ownedFeatureChaining:
            self.ownedFeatureChaining.extend(ownedFeatureChaining)

        if ownedFeatureInverting:
            self.ownedFeatureInverting.extend(ownedFeatureInverting)

        if ownedRedefinition:
            self.ownedRedefinition.extend(ownedRedefinition)

        if ownedReferenceSubsetting is not None:
            self.ownedReferenceSubsetting = ownedReferenceSubsetting

        if ownedSubsetting:
            self.ownedSubsetting.extend(ownedSubsetting)

        if ownedTypeFeaturing:
            self.ownedTypeFeaturing.extend(ownedTypeFeaturing)

        if ownedTyping:
            self.ownedTyping.extend(ownedTyping)

        if owningFeatureMembership is not None:
            self.owningFeatureMembership = owningFeatureMembership

        if owningType is not None:
            self.owningType = owningType

        if type:
            self.type.extend(type)

    def allRedefinedFeatures(self):
        """<p>Return this <code>Feature</code> and all the <code>Features</code> that are directly or indirectly <code>Redefined</code> by this <code>Feature</code>.</p>
ownedRedefinition.redefinedFeature->
    closure(ownedRedefinition.redefinedFeature)->
    asOrderedSet()->prepend(self)
"""
        raise NotImplementedError('operation allRedefinedFeatures(...) not yet implemented')

    def asCartesianProduct(self):
        """<p>If <code>isCartesianProduct</code> is true, then return the list of <code>Types</code> whose Cartesian product can be represented by this <code>Feature</code>. (If <code>isCartesianProduct</code> is not true, the operation will still return a valid value, it will just not represent anything useful.)</p>
featuringType->select(t | t.owner <> self)->
    union(featuringType->select(t | t.owner = self)->
        selectByKind(Feature).asCartesianProduct())->
    union(type)"""
        raise NotImplementedError('operation asCartesianProduct(...) not yet implemented')

    def canAccess(self, feature=None):
        """<p>A <code>Feature</code> can access another <code>feature</code> if the other <code>feature</code> is featured within one of the direct or indirect <code>featuringTypes</code> of this <code>Feature</code>.</p>
let anythingType: Element =
    subsettingFeature.resolveGlobal('Base::Anything').memberElement in
let allFeaturingTypes : Sequence(Type) =
    featuringTypes->closure(t |
        if not t.oclIsKindOf(Feature) then Sequence{}
        else
            let featuringTypes : OrderedSet(Type) = t.oclAsType(Feature).featuringType in
            if featuringTypes->isEmpty() then Sequence{anythingType}
            else featuringTypes
            endif 
        endif) in
allFeaturingTypes->exists(t | feature.isFeaturedWithin(t))"""
        raise NotImplementedError('operation canAccess(...) not yet implemented')

    def directionFor(self, type=None):
        """<p>Return the <code>directionOf</code> this <code>Feature</code> relative to the given <code>type</code>.</p>
type.directionOf(self)"""
        raise NotImplementedError('operation directionFor(...) not yet implemented')

    def isCartesianProduct(self):
        """<p>Check whether this <code>Feature</code> can be used to represent a Cartesian product of <code>Types</code>.</p>
type->size() = 1 and
featuringType.size() = 1 and
(featuringType.first().owner = self implies
    featuringType.first().oclIsKindOf(Feature) and
    featuringType.first().oclAsType(Feature).isCartesianProduct())"""
        raise NotImplementedError('operation isCartesianProduct(...) not yet implemented')

    def isFeaturedWithin(self, type=None):
        """<p>Return if the <code>featuringTypes</code> of this <code>Feature</code> are compatible with the given <code>type</code>. If <code>type</code> is null, then check if this <code>Feature</code> is explicitly or implicitly featured by <em><code>Base::Anything</code></em>. If this <code>Feature</code> has <code>isVariable = true</code>, then also consider it to be featured within its <code>owningType</code>. If this <code>Feature</code> is a feature chain whose first <code>chainingFeature</code> has <code>isVariable = true</code>, then also consider it to be featured within the <code>owningType</code> of its first <code>chainingFeature</code>.</p>
if type = null then
    featuringType->forAll(f | f = resolveGlobal('Base::Anything').memberElement)
else
    featuringType->forAll(f | type.isCompatibleWith(f)) or
    isVariable and type.specializes(owningType) or
    chainingFeature->notEmpty() and chainingFeature->first().isVariable and
        type.specializes(chainingFeature->first().owningType)
endif"""
        raise NotImplementedError('operation isFeaturedWithin(...) not yet implemented')

    def isFeaturingType(self, type=None):
        """<p>Return whether the given <code>type</code> must be a <code>featuringType</code> of this <code>Feature</code>. If this <code>Feature</code> has <code>isVariable = false</code>, then return true if the <code>type</code> is the <code>owningType</code> of the <code>Feature</code>. If <code>isVariable = true</code>, then return true if the <code>type</code> is a <code>Feature</code> representing the <em><code>snapshots</code></em> of the <code>owningType</code> of this <code>Feature</code>.</p>
owningType <> null and
if not isVariable then type = owningType
else if owningType = resolveGlobal('Occurrences::Occurrence').memberElement then
    type = resolveGlobal('Occurrences::Occurrence::snapshots').memberElement 
else 
    type.oclIsKindOf(Feature) and
    let feature : Feature = type.oclAsType(Feature) in
    feature.featuringType->includes(owningType) and
    feature.redefinesFromLibrary('Occurrences::Occurrence::snapshots')
endif
"""
        raise NotImplementedError('operation isFeaturingType(...) not yet implemented')

    def isOwnedCrossFeature(self):
        """<p>Return whether this <code>Feature</code> is an owned cross <code>Feature</code> of an end <code>Feature</code>.</p>
owningNamespace <> null and 
owningNamespace.oclIsKindOf(Feature) and 
owningNamespace.oclAsType(Feature).ownedCrossFeature() = self"""
        raise NotImplementedError('operation isOwnedCrossFeature(...) not yet implemented')

    def namingFeature(self):
        """<p>By default, the naming <code>Feature</code> of a <code>Feature</code> is given by its first <code>redefinedFeature</code> of its first <code>ownedRedefinition</code>, if any.</p>
if ownedRedefinition->isEmpty() then
    null
else
    ownedRedefinition->at(1).redefinedFeature
endif"""
        raise NotImplementedError('operation namingFeature(...) not yet implemented')

    def ownedCrossFeature(self):
        """<p>If this <code>Feature</code> is an end <code>Feature</code> of its <code>owningType</code>, then return the first <code>ownedMember</code> of the <code>Feature</code> that is a <code>Feature</code>, but not a <code>Multiplicity</code> or a <code>MetadataFeature</code>, and whose <code>owningMembership</code> is <em>not</em> a <code>FeatureMembership</code>. If this exists, it is the <code>crossFeature</code> of the end <code>Feature</code>.</p>
if not isEnd or owningType = null then null
else
    let ownedMemberFeatures: Sequence(Feature) =
        ownedMember->selectByKind(Feature)->
            reject(oclIsKindOf(Multiplicity) or 
                   oclIsKindOf(MetadataFeature) or
                   oclIsKindOf(FeatureValue))->
            reject(owningMembership.oclIsKindOf(FeatureMembership)) in
    if ownedMemberFeatures.isEmpty() then null
    else ownedMemberFeatures->first()
    endif"""
        raise NotImplementedError('operation ownedCrossFeature(...) not yet implemented')

    def redefines(self, redefinedFeature=None):
        """<p>Check whether this <code>Feature</code> <em>directly</em> redefines the given <code>redefinedFeature</code>.</p>
ownedRedefinition.redefinedFeature->includes(redefinedFeature)"""
        raise NotImplementedError('operation redefines(...) not yet implemented')

    def redefinesFromLibrary(self, libraryFeatureName=None):
        """<p>Check whether this <code>Feature</code> <em>directly</em> redefines the named library <code>Feature</code>. <code>libraryFeatureName</code> must conform to the syntax of a KerML qualified name and must resolve to a <code>Feature</code> in global scope.</p>
let mem: Membership = resolveGlobal(libraryFeatureName) in
mem <> null and mem.memberElement.oclIsKindOf(Feature) and
redefines(mem.memberElement.oclAsType(Feature))"""
        raise NotImplementedError('operation redefinesFromLibrary(...) not yet implemented')

    def subsetsChain(self, first=None, second=None):
        """<p>Check whether this <code>Feature</code> directly or indirectly specializes a <code>Feature</code> whose last two <code>chainingFeatures</code> are the given <code>Features</code> <code>first</code> and <code>second</code>.</p>
allSuperTypes()->selectAsKind(Feature)->
    exists(f | let n: Integer = f.chainingFeature->size() in
        n >= 2 and
        f.chainingFeature->at(n-1) = first and
        f.chainingFeature->at(n) = second)"""
        raise NotImplementedError('operation subsetsChain(...) not yet implemented')

    def typingFeatures(self):
        """<p>Return the <code>Features</code> used to determine the <code>types</code> of this <code>Feature</code> (other than this <code>Feature</code> itself). If this <code>Feature</code> is <em>not</em> conjugated, then the <code>typingFeatures</code> consist of all subsetted <code>Features</code>, <em>except</em> from <code>CrossSubsetting</code>, and the last <code>chainingFeature</code> (if any). If this <code>Feature</code> <em>is</em> conjugated, then the <code>typingFeatures</code> are only its <code>originalType</code> (if the <code>originalType</code> is a <code>Feature</code>).</p>

<p><strong>Note.</strong> <code>CrossSubsetting</code> is excluded from the determination of the <code>type</code> of a <code>Feature</code> in order to avoid circularity in the construction of implied <code>CrossSubsetting</code> relationships. The <code>validateFeatureCrossFeatureType</code> requires that the <code>crossFeature</code> of a <code>Feature</code> have the same <code>type</code> as the <code>Feature</code>.</p>

if not isConjugated then
    let subsettedFeatures : OrderedSet(Feature) = 
        subsetting->reject(s | s.oclIsKindOf(CrossSubsetting)).subsettedFeatures in 
    if chainingFeature->isEmpty() or
       subsettedFeature->includes(chainingFeature->last())
    then subsettedFeatures
    else subsettedFeatures->append(chainingFeature->last())
    endif
else if conjugator.originalType.oclIsKindOf(Feature) then
    OrderedSet{conjugator.originalType.oclAsType(Feature)}
else OrderedSet{}
endif endif"""
        raise NotImplementedError('operation typingFeatures(...) not yet implemented')


class FeatureTyping(Specialization):
    """<p><code>FeatureTyping</code> is <code>Specialization</code> in which the <code>specific</code> <code>Type</code> is a <code>Feature</code>. This means the set of instances of the (specific) <code>typedFeature</code> is a subset of the set of instances of the (general) <code>type</code>. In the simplest case, the <code>type</code> is a <code>Classifier</code>, whereupon the <code>typedFeature</code> has values that are instances of the <code>Classifier</code>.</p>
"""
    _owningFeature = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='owningFeature', transient=True)
    type = EReference(ordered=False, unique=True, containment=False, derived=False)
    typedFeature = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def owningFeature(self):
        raise NotImplementedError('Missing implementation for owningFeature')

    @owningFeature.setter
    def owningFeature(self, value):
        raise NotImplementedError('Missing implementation for owningFeature')

    def __init__(self, *, owningFeature=None, type=None, typedFeature=None, **kwargs):

        super().__init__(**kwargs)

        if owningFeature is not None:
            self.owningFeature = owningFeature

        if type is not None:
            self.type = type

        if typedFeature is not None:
            self.typedFeature = typedFeature


class LibraryPackage(Package):
    """<p>A <code>LibraryPackage</code> is a <code>Package</code> that is the container for a model library. A <code>LibraryPackage</code> is itself a library <code>Element</code> as are all <code>Elements</code> that are directly or indirectly contained in it.</p>
"""
    isStandard = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)

    def __init__(self, *, isStandard=None, **kwargs):

        super().__init__(**kwargs)

        if isStandard is not None:
            self.isStandard = isStandard


class MembershipImport(Import):
    """<p>A <code>MembershipImport</code> is an <code>Import</code> that imports its <code>importedMembership</code> into the <code>importOwningNamespace</code>. If <code>isRecursive = true</code> and the <code>memberElement</code> of the <code>importedMembership</code> is a <code>Namespace</code>, then the equivalent of a recursive <code>NamespaceImport</code> is also performed on that <code>Namespace</code>.</p>

importedElement = importedMembership.memberElement"""
    importedMembership = EReference(ordered=False, unique=True, containment=False, derived=False)

    def __init__(self, *, importedMembership=None, **kwargs):

        super().__init__(**kwargs)

        if importedMembership is not None:
            self.importedMembership = importedMembership


class NamespaceImport(Import):
    """<p>A <code>NamespaceImport</code> is an Import that imports <code>Memberships</code> from its <code>importedNamespace</code> into the <code>importOwningNamespace</code>. If <code> isRecursive = false</code>, then only the visible <code>Memberships</code> of the <code>importedNamespace</code> are imported. If <code> isRecursive = true</code>, then, in addition, <code>Memberships</code> are recursively imported from any <code>ownedMembers</code> of the <code>importedNamespace</code> that are <code>Namespaces</code>.</p>

importedElement = importedNamespace"""
    importedNamespace = EReference(ordered=False, unique=True, containment=False, derived=False)

    def __init__(self, *, importedNamespace=None, **kwargs):

        super().__init__(**kwargs)

        if importedNamespace is not None:
            self.importedNamespace = importedNamespace


class OwningMembership(Membership):
    """<p>An <code>OwningMembership</code> is a <code>Membership</code> that owns its <code>memberElement</code> as a <code>ownedRelatedElement</code>. The <code>ownedMemberElement</code> becomes an <code>ownedMember</code> of the <code>membershipOwningNamespace</code>.</p>

ownedMemberName = ownedMemberElement.name
ownedMemberShortName = ownedMemberElement.shortName"""
    _ownedMemberElementId = EAttribute(
        eType=EString, unique=True, derived=True, changeable=True, name='ownedMemberElementId', transient=True)
    _ownedMemberName = EAttribute(eType=EString, unique=True, derived=True,
                                  changeable=True, name='ownedMemberName', transient=True)
    _ownedMemberShortName = EAttribute(
        eType=EString, unique=True, derived=True, changeable=True, name='ownedMemberShortName', transient=True)
    _ownedMemberElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedMemberElement', transient=True)

    @property
    def ownedMemberElement(self):
        raise NotImplementedError('Missing implementation for ownedMemberElement')

    @ownedMemberElement.setter
    def ownedMemberElement(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberElement')

    @property
    def ownedMemberElementId(self):
        raise NotImplementedError('Missing implementation for ownedMemberElementId')

    @ownedMemberElementId.setter
    def ownedMemberElementId(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberElementId')

    @property
    def ownedMemberName(self):
        raise NotImplementedError('Missing implementation for ownedMemberName')

    @ownedMemberName.setter
    def ownedMemberName(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberName')

    @property
    def ownedMemberShortName(self):
        raise NotImplementedError('Missing implementation for ownedMemberShortName')

    @ownedMemberShortName.setter
    def ownedMemberShortName(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberShortName')

    def __init__(self, *, ownedMemberElement=None, ownedMemberElementId=None, ownedMemberName=None, ownedMemberShortName=None, **kwargs):

        super().__init__(**kwargs)

        if ownedMemberElementId is not None:
            self.ownedMemberElementId = ownedMemberElementId

        if ownedMemberName is not None:
            self.ownedMemberName = ownedMemberName

        if ownedMemberShortName is not None:
            self.ownedMemberShortName = ownedMemberShortName

        if ownedMemberElement is not None:
            self.ownedMemberElement = ownedMemberElement


class PortConjugation(Conjugation):
    """<p>A <code>PortConjugation</code> is a <code>Conjugation</code> <code>Relationship</code> between a <code>PortDefinition</code> and its corresponding <code>ConjugatedPortDefinition</code>. As a result of this <code>Relationship</code>, the <code>ConjugatedPortDefinition</code> inherits all the <code>features</code> of the original <code>PortDefinition</code>, but input <code>flows</code> of the original <code>PortDefinition</code> become outputs on the <code>ConjugatedPortDefinition</code> and output <code>flows</code> of the original <code>PortDefinition</code> become inputs on the <code>ConjugatedPortDefinition</code>.</code></p>
"""
    _conjugatedPortDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='conjugatedPortDefinition', transient=True)
    originalPortDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=False)

    @property
    def conjugatedPortDefinition(self):
        raise NotImplementedError('Missing implementation for conjugatedPortDefinition')

    @conjugatedPortDefinition.setter
    def conjugatedPortDefinition(self, value):
        raise NotImplementedError('Missing implementation for conjugatedPortDefinition')

    def __init__(self, *, conjugatedPortDefinition=None, originalPortDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if conjugatedPortDefinition is not None:
            self.conjugatedPortDefinition = conjugatedPortDefinition

        if originalPortDefinition is not None:
            self.originalPortDefinition = originalPortDefinition


class Subclassification(Specialization):
    """<p><code>Subclassification</code> is <code>Specialization</code> in which both the <code>specific</code> and <code>general</code> <code>Types</code> are <code>Classifier</code>. This means all instances of the specific <code>Classifier</code> are also instances of the general <code>Classifier</code>.</p>
"""
    _owningClassifier = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='owningClassifier', transient=True)
    subclassifier = EReference(ordered=False, unique=True, containment=False, derived=False)
    superclassifier = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def owningClassifier(self):
        raise NotImplementedError('Missing implementation for owningClassifier')

    @owningClassifier.setter
    def owningClassifier(self, value):
        raise NotImplementedError('Missing implementation for owningClassifier')

    def __init__(self, *, owningClassifier=None, subclassifier=None, superclassifier=None, **kwargs):

        super().__init__(**kwargs)

        if owningClassifier is not None:
            self.owningClassifier = owningClassifier

        if subclassifier is not None:
            self.subclassifier = subclassifier

        if superclassifier is not None:
            self.superclassifier = superclassifier


class Subsetting(Specialization):
    """<p><code>Subsetting</code> is <code>Specialization</code> in which the <code>specific</code> and <code>general</code> <code>Types</code> are <code>Features</code>. This means all values of the <code>subsettingFeature</code> (on instances of its domain, i.e., the intersection of its <code>featuringTypes</code>) are values of the <code>subsettedFeature</code> on instances of its domain. To support this the domain of the <code>subsettingFeature</code> must be the same or specialize (at least indirectly) the domain of the <code>subsettedFeature</code> (via <code>Specialization</code>), and the co-domain (intersection of the <code>types</code>) of the <code>subsettingFeature</code> must specialize the co-domain of the <code>subsettedFeature</code>.</p>

subsettingFeature.canAccess(subsettedFeature)
subsettedFeature.isUnique implies subsettingFeature.isUnique
subsettedFeature.isConstant and subsettingFeature.isVariable implies 
    subsettingFeature.isConstant
"""
    _owningFeature = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='owningFeature', transient=True)
    subsettedFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    subsettingFeature = EReference(ordered=False, unique=True, containment=False, derived=False)

    @property
    def owningFeature(self):
        raise NotImplementedError('Missing implementation for owningFeature')

    @owningFeature.setter
    def owningFeature(self, value):
        raise NotImplementedError('Missing implementation for owningFeature')

    def __init__(self, *, owningFeature=None, subsettedFeature=None, subsettingFeature=None, **kwargs):

        super().__init__(**kwargs)

        if owningFeature is not None:
            self.owningFeature = owningFeature

        if subsettedFeature is not None:
            self.subsettedFeature = subsettedFeature

        if subsettingFeature is not None:
            self.subsettingFeature = subsettingFeature


class Class(Classifier):
    """<p>A <code>Class</code> is a <code>Classifier</code> of things (in the universe) that can be distinguished without regard to how they are related to other things (via <code>Features</code>). This means multiple things classified by the same <code>Class</code> can be distinguished, even when they are related other things in exactly the same way.</p>

specializesFromLibrary('Occurrences::Occurrence')
ownedSpecialization.general->
    forAll(not oclIsKindOf(DataType)) and
not oclIsKindOf(Association) implies
    ownedSpecialization.general->
        forAll(not oclIsKindOf(Association))"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class ConjugatedPortTyping(FeatureTyping):
    """<p>A <code>ConjugatedPortTyping</code> is a <code>FeatureTyping</code> whose <code>type</code> is a <code>ConjugatedPortDefinition</code>. (This relationship is intended to be an abstract-syntax marker for a special surface notation for conjugated typing of ports.)</p>
portDefinition = conjugatedPortDefinition.originalPortDefinition"""
    conjugatedPortDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=False)
    _portDefinition = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='portDefinition', transient=True)

    @property
    def portDefinition(self):
        raise NotImplementedError('Missing implementation for portDefinition')

    @portDefinition.setter
    def portDefinition(self, value):
        raise NotImplementedError('Missing implementation for portDefinition')

    def __init__(self, *, conjugatedPortDefinition=None, portDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if conjugatedPortDefinition is not None:
            self.conjugatedPortDefinition = conjugatedPortDefinition

        if portDefinition is not None:
            self.portDefinition = portDefinition


class CrossSubsetting(Subsetting):
    """<p><code>CrossSubsetting</code> is a kind of <code>Subsetting</code> for end <code>Features</code>, as identified by <code>crossingFeature</code>, to subset a chained <code>Feature</code>, identified by <code>crossedFeature.</code> It navigates to instances of the end <code>Feature</code>’s type from instances of other end <code>Feature</code> types on the same <code>owningType</code> (at least two end <code>Features</code> are required for any of them to have a <code>CrossSubsetting</code>).</p>

<p>The <code>crossedFeature</code> of a <code>CrossSubsetting</code> must have a feature chain of exactly two <code>Features</code>. The second <code>Feature</code> in the chain is the <code>crossFeature</code> of the <code>crossingFeature</code> (end <code>Feature</code>), which has the same type as the <code>crossingFeature</code>. When the <code>owningType</code> of the <code>crossingFeature</code> has exactly two end <code>Features</code>, the first <code>Feature</code> in the chain of the <code>crossedFeature</code> is the other end <code>Feature</code>. The <code>crossFeature</code>’s <code>featuringType</code> in this case is the other end <code>Feature</code>. When the <code>owningType</code> has more than two end <code>Features</code>, the first <code>Feature</code> in the chain is a <code>Feature</code> that <code>CrossMultiplies</code> all the other end <code>Features</code>, which is also the <code>featuringType</code> of the <code>crossFeature</code>.</p>

<p>A <code>crossFeature</code> must be owned by its <code>featureCrossing</code> (end <code>Feature</code>) when the <code>featureCrossing</code> <code>owningType</code> has more than two end <code>Features</code>. Otherwise, for exactly two end <code>Features</code>, the <code>crossFeatures</code> of each the ends can instead optionally be inherited by the other end from one of its <code>types</code> or a subsetted <code>Feature</code>.</p>
crossingFeature.isEnd and crossingFeature.owningType <> null implies
    let endFeatures: Sequence(Feature) = crossingFeature.owningType.endFeature in
    let chainingFeatures: Sequence(Feature) = crossedFeature.chainingFeature in
    chainingFeatures->size() = 2 and
    endFeatures->size() = 2 implies 
        chainingFeatures->at(1) = endFeatures->excluding(crossingFeature)->at(1)
crossingFeature.isEnd and
crossingFeature.owningType<>null and
crossingFeature.owningType.endFeature ->size() > 1"""
    crossedFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    _crossingFeature = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='crossingFeature', transient=True)

    @property
    def crossingFeature(self):
        raise NotImplementedError('Missing implementation for crossingFeature')

    @crossingFeature.setter
    def crossingFeature(self, value):
        raise NotImplementedError('Missing implementation for crossingFeature')

    def __init__(self, *, crossedFeature=None, crossingFeature=None, **kwargs):

        super().__init__(**kwargs)

        if crossedFeature is not None:
            self.crossedFeature = crossedFeature

        if crossingFeature is not None:
            self.crossingFeature = crossingFeature


class DataType(Classifier):
    """<p>A <code>DataType</code> is a <code>Classifier</code> of things (in the universe) that can only be distinguished by how they are related to other things (via Features). This means multiple things classified by the same <code>DataType</code></p>

<ul>
        <li>Cannot be distinguished when they are related to other things in exactly the same way, even when they are intended to be about different things.</li>
        <li>Can be distinguished when they are related to other things in different ways, even when they are intended to be about the same thing.</li>
</ul>

ownedSpecialization.general->
    forAll(not oclIsKindOf(Class) and 
           not oclIsKindOf(Association))
specializesFromLibrary('Base::DataValue')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedDirectedusage(EDerivedCollection):
    pass


class DerivedOwnedaction(EDerivedCollection):
    pass


class DerivedOwnedallocation(EDerivedCollection):
    pass


class DerivedOwnedanalysiscase(EDerivedCollection):
    pass


class DerivedOwnedattribute(EDerivedCollection):
    pass


class DerivedOwnedcalculation(EDerivedCollection):
    pass


class DerivedOwnedcase(EDerivedCollection):
    pass


class DerivedOwnedconcern(EDerivedCollection):
    pass


class DerivedOwnedconnection(EDerivedCollection):
    pass


class DerivedOwnedconstraint(EDerivedCollection):
    pass


class DerivedOwnedenumeration(EDerivedCollection):
    pass


class DerivedOwnedflow(EDerivedCollection):
    pass


class DerivedOwnedinterface(EDerivedCollection):
    pass


class DerivedOwneditem(EDerivedCollection):
    pass


class DerivedOwnedmetadata(EDerivedCollection):
    pass


class DerivedOwnedoccurrence(EDerivedCollection):
    pass


class DerivedOwnedpart(EDerivedCollection):
    pass


class DerivedOwnedport(EDerivedCollection):
    pass


class DerivedOwnedreference(EDerivedCollection):
    pass


class DerivedOwnedrendering(EDerivedCollection):
    pass


class DerivedOwnedrequirement(EDerivedCollection):
    pass


class DerivedOwnedstate(EDerivedCollection):
    pass


class DerivedOwnedtransition(EDerivedCollection):
    pass


class DerivedOwnedusage(EDerivedCollection):
    pass


class DerivedOwnedusecase(EDerivedCollection):
    pass


class DerivedOwnedverificationcase(EDerivedCollection):
    pass


class DerivedOwnedview(EDerivedCollection):
    pass


class DerivedOwnedviewpoint(EDerivedCollection):
    pass


class DerivedUsage(EDerivedCollection):
    pass


class DerivedVariant(EDerivedCollection):
    pass


class DerivedVariantmembership(EDerivedCollection):
    pass


class Definition(Classifier):
    """<p>A <code>Definition</code> is a <code>Classifier</code> of <code>Usages</code>. The actual kinds of <code>Definition</code> that may appear in a model are given by the subclasses of <code>Definition</code> (possibly as extended with user-defined <em><code>SemanticMetadata</code></em>).</p>

<p>Normally, a <code>Definition</code> has owned Usages that model <code>features</code> of the thing being defined. A <code>Definition</code> may also have other <code>Definitions</code> nested in it, but this has no semantic significance, other than the nested scoping resulting from the <code>Definition</code> being considered as a <code>Namespace</code> for any nested <code>Definitions</code>.</p>

<p>However, if a <code>Definition</code> has <code>isVariation</code> = <code>true</code>, then it represents a <em>variation point</em> <code>Definition</code>. In this case, all of its <code>members</code> must be <code>variant</code> <code>Usages</code>, related to the <code>Definition</code> by <code>VariantMembership</code> <code>Relationships</code>. Rather than being <code>features</code> of the <code>Definition</code>, <code>variant</code> <code>Usages</code> model different concrete alternatives that can be chosen to fill in for an abstract <code>Usage</code> of the variation point <code>Definition</code>.</p>

isVariation implies ownedFeatureMembership->isEmpty()
variant = variantMembership.ownedVariantUsage
variantMembership = ownedMembership->selectByKind(VariantMembership)
isVariation implies
    not ownedSpecialization.specific->exists(
        oclIsKindOf(Definition) and
        oclAsType(Definition).isVariation)
usage = feature->selectByKind(Usage)
directedUsage = directedFeature->selectByKind(Usage)
ownedUsage = ownedFeature->selectByKind(Usage)
ownedAttribute = ownedUsage->selectByKind(AttributeUsage)
ownedReference = ownedUsage->selectByKind(ReferenceUsage)
ownedEnumeration = ownedUsage->selectByKind(EnumerationUsage)
ownedOccurrence = ownedUsage->selectByKind(OccurrenceUsage)
ownedItem = ownedUsage->selectByKind(ItemUsage)
ownedPart = ownedUsage->selectByKind(PartUsage)
ownedPort = ownedUsage->selectByKind(PortUsage)
ownedConnection = ownedUsage->selectByKind(ConnectorAsUsage)
ownedFlow = ownedUsage->selectByKind(FlowUsage)
ownedInterface = ownedUsage->selectByKind(ReferenceUsage)
ownedAllocation = ownedUsage->selectByKind(AllocationUsage)
ownedAction = ownedUsage->selectByKind(ActionUsage)
ownedState = ownedUsage->selectByKind(StateUsage)
ownedTransition = ownedUsage->selectByKind(TransitionUsage)
ownedCalculation = ownedUsage->selectByKind(CalculationUsage)
ownedConstraint = ownedUsage->selectByKind(ConstraintUsage)
ownedRequirement = ownedUsage->selectByKind(RequirementUsage)
ownedConcern = ownedUsage->selectByKind(ConcernUsage)
ownedCase = ownedUsage->selectByKind(CaseUsage)
ownedAnalysisCase = ownedUsage->selectByKind(AnalysisCaseUsage)
ownedVerificationCase = ownedUsage->selectByKind(VerificationCaseUsage)
ownedUseCase = ownedUsage->selectByKind(UseCaseUsage)
ownedView = ownedUsage->selectByKind(ViewUsage)
ownedViewpoint = ownedUsage->selectByKind(ViewpointUsage)
ownedRendering = ownedUsage->selectByKind(RenderingUsage)
ownedMetadata = ownedMember->selectByKind(MetadataUsage)
isVariation implies isAbstract"""
    isVariation = EAttribute(eType=EBoolean, unique=True, derived=False, changeable=True)
    directedUsage = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedDirectedusage)
    ownedAction = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedOwnedaction)
    ownedAllocation = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedallocation)
    ownedAnalysisCase = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedOwnedanalysiscase)
    ownedAttribute = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedOwnedattribute)
    ownedCalculation = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedOwnedcalculation)
    ownedCase = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwnedcase)
    ownedConcern = EReference(ordered=False, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedOwnedconcern)
    ownedConnection = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedconnection)
    ownedConstraint = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedconstraint)
    ownedEnumeration = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedOwnedenumeration)
    ownedFlow = EReference(ordered=False, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwnedflow)
    ownedInterface = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedOwnedinterface)
    ownedItem = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwneditem)
    ownedMetadata = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedOwnedmetadata)
    ownedOccurrence = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedoccurrence)
    ownedPart = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwnedpart)
    ownedPort = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwnedport)
    ownedReference = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedOwnedreference)
    ownedRendering = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedOwnedrendering)
    ownedRequirement = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedOwnedrequirement)
    ownedState = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedOwnedstate)
    ownedTransition = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedOwnedtransition)
    ownedUsage = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedOwnedusage)
    ownedUseCase = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedOwnedusecase)
    ownedVerificationCase = EReference(ordered=True, unique=True, containment=False,
                                       derived=True, upper=-1, transient=True, derived_class=DerivedOwnedverificationcase)
    ownedView = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedOwnedview)
    ownedViewpoint = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedOwnedviewpoint)
    usage = EReference(ordered=True, unique=True, containment=False, derived=True,
                       upper=-1, transient=True, derived_class=DerivedUsage)
    variant = EReference(ordered=False, unique=True, containment=False,
                         derived=True, upper=-1, transient=True, derived_class=DerivedVariant)
    variantMembership = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedVariantmembership)

    def __init__(self, *, directedUsage=None, isVariation=None, ownedAction=None, ownedAllocation=None, ownedAnalysisCase=None, ownedAttribute=None, ownedCalculation=None, ownedCase=None, ownedConcern=None, ownedConnection=None, ownedConstraint=None, ownedEnumeration=None, ownedFlow=None, ownedInterface=None, ownedItem=None, ownedMetadata=None, ownedOccurrence=None, ownedPart=None, ownedPort=None, ownedReference=None, ownedRendering=None, ownedRequirement=None, ownedState=None, ownedTransition=None, ownedUsage=None, ownedUseCase=None, ownedVerificationCase=None, ownedView=None, ownedViewpoint=None, usage=None, variant=None, variantMembership=None, **kwargs):

        super().__init__(**kwargs)

        if isVariation is not None:
            self.isVariation = isVariation

        if directedUsage:
            self.directedUsage.extend(directedUsage)

        if ownedAction:
            self.ownedAction.extend(ownedAction)

        if ownedAllocation:
            self.ownedAllocation.extend(ownedAllocation)

        if ownedAnalysisCase:
            self.ownedAnalysisCase.extend(ownedAnalysisCase)

        if ownedAttribute:
            self.ownedAttribute.extend(ownedAttribute)

        if ownedCalculation:
            self.ownedCalculation.extend(ownedCalculation)

        if ownedCase:
            self.ownedCase.extend(ownedCase)

        if ownedConcern:
            self.ownedConcern.extend(ownedConcern)

        if ownedConnection:
            self.ownedConnection.extend(ownedConnection)

        if ownedConstraint:
            self.ownedConstraint.extend(ownedConstraint)

        if ownedEnumeration:
            self.ownedEnumeration.extend(ownedEnumeration)

        if ownedFlow:
            self.ownedFlow.extend(ownedFlow)

        if ownedInterface:
            self.ownedInterface.extend(ownedInterface)

        if ownedItem:
            self.ownedItem.extend(ownedItem)

        if ownedMetadata:
            self.ownedMetadata.extend(ownedMetadata)

        if ownedOccurrence:
            self.ownedOccurrence.extend(ownedOccurrence)

        if ownedPart:
            self.ownedPart.extend(ownedPart)

        if ownedPort:
            self.ownedPort.extend(ownedPort)

        if ownedReference:
            self.ownedReference.extend(ownedReference)

        if ownedRendering:
            self.ownedRendering.extend(ownedRendering)

        if ownedRequirement:
            self.ownedRequirement.extend(ownedRequirement)

        if ownedState:
            self.ownedState.extend(ownedState)

        if ownedTransition:
            self.ownedTransition.extend(ownedTransition)

        if ownedUsage:
            self.ownedUsage.extend(ownedUsage)

        if ownedUseCase:
            self.ownedUseCase.extend(ownedUseCase)

        if ownedVerificationCase:
            self.ownedVerificationCase.extend(ownedVerificationCase)

        if ownedView:
            self.ownedView.extend(ownedView)

        if ownedViewpoint:
            self.ownedViewpoint.extend(ownedViewpoint)

        if usage:
            self.usage.extend(usage)

        if variant:
            self.variant.extend(variant)

        if variantMembership:
            self.variantMembership.extend(variantMembership)


class ElementFilterMembership(OwningMembership):
    """<p><code>ElementFilterMembership</code> is a <code>Membership</code> between a <code>Namespace</code> and a model-level evaluable <code><em>Boolean</em></code>-valued <code>Expression</code>, asserting that imported <code>members</code> of the <code>Namespace</code> should be filtered using the <code>condition</code> <code>Expression</code>. A general <code>Namespace</code> does not define any specific filtering behavior, but such behavior may be defined for various specialized kinds of <code>Namespaces</code>.</p>

condition.isModelLevelEvaluable
condition.result.specializesFromLibrary('ScalarValues::Boolean')"""
    _condition = EReference(ordered=False, unique=True, containment=False,
                            derived=True, name='condition', transient=True)

    @property
    def condition(self):
        raise NotImplementedError('Missing implementation for condition')

    @condition.setter
    def condition(self, value):
        raise NotImplementedError('Missing implementation for condition')

    def __init__(self, *, condition=None, **kwargs):

        super().__init__(**kwargs)

        if condition is not None:
            self.condition = condition


class FeatureMembership(OwningMembership):
    """<p>A <code>FeatureMembership</code> is an <code>OwningMembership</code> between an <code>ownedMemberFeature</code> and an <code>owningType</code>. If the <code>ownedMemberFeature</code> has <code>isVariable = false</code>, then the <code>FeatureMembership</code> implies that the <code>owningType</code> is also a <code>featuringType</code> of the <code>ownedMemberFeature</code>. If the <code>ownedMemberFeature</code> has <code>isVariable = true</code>, then the <code>FeatureMembership</code> implies that the <code>ownedMemberFeature</code> is featured by the <em><code>snapshots</code></em> of the <code>owningType</code>, which must specialize the Kernel Semantic Library base class <em><code>Occurrence</code></em>.</p>
"""
    _ownedMemberFeature = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedMemberFeature', transient=True)
    _owningType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='owningType', transient=True)

    @property
    def ownedMemberFeature(self):
        raise NotImplementedError('Missing implementation for ownedMemberFeature')

    @ownedMemberFeature.setter
    def ownedMemberFeature(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberFeature')

    @property
    def owningType(self):
        raise NotImplementedError('Missing implementation for owningType')

    @owningType.setter
    def owningType(self, value):
        raise NotImplementedError('Missing implementation for owningType')

    def __init__(self, *, ownedMemberFeature=None, owningType=None, **kwargs):

        super().__init__(**kwargs)

        if ownedMemberFeature is not None:
            self.ownedMemberFeature = ownedMemberFeature

        if owningType is not None:
            self.owningType = owningType


class FeatureValue(OwningMembership):
    """<p>A <code>FeatureValue</code> is a <code>Membership</code> that identifies a particular member <code>Expression</code> that provides the value of the <code>Feature</code> that owns the <code>FeatureValue</code>. The value is specified as either a bound value or an initial value, and as either a concrete or default value. A <code>Feature</code> can have at most one <code>FeatureValue</code>.</p>

<p>The result of the <code>value</code> <code>Expression</code> is bound to the <code>featureWithValue</code> using a <code>BindingConnector</code>. If <code>isInitial = false</code>, then the <code>featuringType</code> of the <code>BindingConnector</code> is the same as the <code>featuringType</code> of the <code>featureWithValue</code>. If <code>isInitial = true</code>, then the <code>featuringType</code> of the <code>BindingConnector</code> is restricted to its <code>startShot</code>.

<p>If <code>isDefault = false</code>, then the above semantics of the <code>FeatureValue</code> are realized for the given <code>featureWithValue</code>. Otherwise, the semantics are realized for any individual of the <code>featuringType</code> of the <code>featureWithValue</code>, unless another value is explicitly given for the <code>featureWithValue</code> for that individual.</p>

not isDefault implies
    featureWithValue.ownedMember->
        selectByKind(BindingConnector)->exists(b |
            b.relatedFeature->includes(featureWithValue) and
            b.relatedFeature->exists(f | 
                f.chainingFeature = Sequence{value, value.result}) and
            if not isInitial then 
                b.featuringType = featureWithValue.featuringType
            else 
                b.featuringType->exists(t |
                    t.oclIsKindOf(Feature) and
                    t.oclAsType(Feature).chainingFeature =
                        Sequence{
                            resolveGlobal('Base::things::that').
                                memberElement,
                            resolveGlobal('Occurrences::Occurrence::startShot').
                                memberElement
                        }
                )
            endif)
featureWithValue.redefinition.redefinedFeature->
    closure(redefinition.redefinedFeature).valuation->
    forAll(isDefault)
isInitial implies featureWithValue.isVariable"""
    isDefault = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    isInitial = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)
    _featureWithValue = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='featureWithValue', transient=True)
    _value = EReference(ordered=False, unique=True, containment=False,
                        derived=True, name='value', transient=True)

    @property
    def featureWithValue(self):
        raise NotImplementedError('Missing implementation for featureWithValue')

    @featureWithValue.setter
    def featureWithValue(self, value):
        raise NotImplementedError('Missing implementation for featureWithValue')

    @property
    def value(self):
        raise NotImplementedError('Missing implementation for value')

    @value.setter
    def value(self, value):
        raise NotImplementedError('Missing implementation for value')

    def __init__(self, *, featureWithValue=None, isDefault=None, isInitial=None, value=None, **kwargs):

        super().__init__(**kwargs)

        if isDefault is not None:
            self.isDefault = isDefault

        if isInitial is not None:
            self.isInitial = isInitial

        if featureWithValue is not None:
            self.featureWithValue = featureWithValue

        if value is not None:
            self.value = value


class FlowEnd(Feature):
    """<p>A <code>FlowEnd</code> is a <code>Feature</code> that is one of the <code>connectorEnds</code> giving the <code><em>source</em></code> or <code><em>target</em></code> of a <code>Flow</code>. For <code>Flows</code> typed by <code><em>FlowTransfer</em></code> or its specializations, <code>FlowEnds</code> must have exactly one <code>ownedFeature</code>, which redefines <code><em>Transfer::source::sourceOutput</em></code> or <code><em>Transfer::target::targetInput</em></code> and redefines the corresponding feature of the <code>relatedElement</code> for its end.</p>
isEnd
ownedFeature->size() = 1
owningType <> null and owningType.oclIsKindOf(Flow)"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class Multiplicity(Feature):
    """<p>A <code>Multiplicity</code> is a <code>Feature</code> whose co-domain is a set of natural numbers giving the allowed cardinalities of each <code>typeWithMultiplicity</code>. The <em>cardinality</em> of a <code>Type</code> is defined as follows, depending on whether the <code>Type</code> is a <code>Classifier</code> or <code>Feature</code>.
<ul>
<li><code>Classifier</code> – The number of basic instances of the <code>Classifier</code>, that is, those instances representing things, which are not instances of any subtypes of the <code>Classifier</code> that are <code>Features</code>.
<li><code>Features</code> – The number of instances with the same featuring instances. In the case of a <code>Feature</code> with a <code>Classifier</code> as its <code>featuringType</code>, this is the number of values of <code>Feature</code> for each basic instance of the <code>Classifier</code>. Note that, for non-unique <code>Features</code>, all duplicate values are included in this count.</li>
</ul>

<p><code>Multiplicity</code> co-domains (in models) can be specified by <code>Expression</code> that might vary in their results. If the <code>typeWithMultiplicity</code> is a <code>Classifier</code>, the domain of the <code>Multiplicity</code> shall be <em><code>Base::Anything</code></em>.  If the <code>typeWithMultiplicity</code> is a <code>Feature</code>,  the <code>Multiplicity</code> shall have the same domain as the <code>typeWithMultiplicity</code>.</p>

if owningNamespace <> null and owningNamespace.oclIsKindOf(Feature) then
    featuringType = 
        owningNamespace.oclAsType(Feature).featuringType
else
    featuringType->isEmpty()
endif
specializesFromLibrary('Base::naturals')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class PayloadFeature(Feature):
    """<p>A <code>PayloadFeature</code> is the <code>ownedFeature</code> of a <code>Flow</code> that identifies the things carried by the kinds of transfers that are instances of the <code>Flow</code>.</p>
redefinesFromLibrary('Transfers::Transfer::payload')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class Redefinition(Subsetting):
    """<p><code>Redefinition</code> is a kind of <code>Subsetting</code> that requires the <code>redefinedFeature</code> and the <code>redefiningFeature</code> to have the same values (on each instance of the domain of the <code>redefiningFeature</code>). This means any restrictions on the <code>redefiningFeature</code>, such as <code>type</code> or <code>multiplicity</code>, also apply to the <code>redefinedFeature</code> (on each instance of the domain of the <code>redefiningFeature</code>), and vice versa. The <code>redefinedFeature</code> might have values for instances of the domain of the <code>redefiningFeature</code>, but only as instances of the domain of the <code>redefinedFeature</code> that happen to also be instances of the domain of the <code>redefiningFeature</code>. This is supported by the constraints inherited from <code>Subsetting</code> on the domains of the <code>redefiningFeature</code> and <code>redefinedFeature</code>. However, these constraints are narrowed for <code>Redefinition</code> to require the <code>owningTypes</code> of the <code>redefiningFeature</code> and <code>redefinedFeature</code> to be different and the <code>redefinedFeature</code> to not be inherited into the <code>owningNamespace</code> of the <code>redefiningFeature</code>.This enables the <code>redefiningFeature</code> to have the same name as the <code>redefinedFeature</code>, if desired.</p>

let anythingType: Type =
    redefiningFeature.resolveGlobal('Base::Anything').modelElement.oclAsType(Type) in 
-- Including "Anything" accounts for implicit featuringType of Features
-- with no explicit featuringType.
let redefiningFeaturingTypes: Set(Type) =
    if redefiningFeature.isVariable then Set{redefiningFeature.owningType}
    else redefiningFeature.featuringTypes->asSet()->including(anythingType) 
    endif in
let redefinedFeaturingTypes: Set(Type) =
    if redefinedFeature.isVariable then Set{redefinedFeature.owningType}
    else redefinedFeature.featuringTypes->asSet()->including(anythingType)
    endif in
redefiningFeaturingTypes <> redefinedFeaturingType
let featuringTypes : Sequence(Type) =
    if redefiningFeature.isVariable then Sequence{redefiningFeature.owningType}
    else redefiningFeature.featuringType
    endif in
featuringTypes->forAll(t |
    let direction : FeatureDirectionKind = t.directionOf(redefinedFeature) in
    ((direction = FeatureDirectionKind::_'in' or 
      direction = FeatureDirectionKind::out) implies
         redefiningFeature.direction = direction)
    and 
    (direction = FeatureDirectionKind::inout implies
        redefiningFeature.direction <> null))
redefinedFeature.isEnd implies redefiningFeature.isEnd"""
    redefinedFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    redefiningFeature = EReference(ordered=False, unique=True, containment=False, derived=False)

    def __init__(self, *, redefinedFeature=None, redefiningFeature=None, **kwargs):

        super().__init__(**kwargs)

        if redefinedFeature is not None:
            self.redefinedFeature = redefinedFeature

        if redefiningFeature is not None:
            self.redefiningFeature = redefiningFeature


class ReferenceSubsetting(Subsetting):
    """<p><code>ReferenceSubsetting</code> is a kind of <code>Subsetting</code> in which the <code>referencedFeature</code> is syntactically distinguished from other <code>Features</code> subsetted by the <code>referencingFeature</code>. <code>ReferenceSubsetting</code> has the same semantics as <code>Subsetting</code>, but the <code>referencedFeature</code> may have a special purpose relative to the <code>referencingFeature</code>. For instance, <code>ReferenceSubsetting</code> is used to identify the <code>relatedFeatures</code> of a <code>Connector</code>.</p>

<p><code>ReferenceSubsetting</code> is always an <code>ownedRelationship</code> of its <code>referencingFeature</code>. A <code>Feature</code> can have at most one <code>ownedReferenceSubsetting</code>.</p>
"""
    referencedFeature = EReference(ordered=False, unique=True, containment=False, derived=False)
    _referencingFeature = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='referencingFeature', transient=True)

    @property
    def referencingFeature(self):
        raise NotImplementedError('Missing implementation for referencingFeature')

    @referencingFeature.setter
    def referencingFeature(self, value):
        raise NotImplementedError('Missing implementation for referencingFeature')

    def __init__(self, *, referencedFeature=None, referencingFeature=None, **kwargs):

        super().__init__(**kwargs)

        if referencedFeature is not None:
            self.referencedFeature = referencedFeature

        if referencingFeature is not None:
            self.referencingFeature = referencingFeature


class DerivedBehavior(EDerivedCollection):
    pass


class DerivedParameter(EDerivedCollection):
    pass


class Step(Feature):
    """<p>A <code>Step</code> is a <code>Feature</code> that is typed by one or more <code>Behaviors</code>. <code>Steps</code> may be used by one <code>Behavior</code> to coordinate the performance of other <code>Behaviors</code>, supporting a steady refinement of behavioral descriptions. <code>Steps</code> can be ordered in time and can be connected using <code>Flows</code> to specify things flowing between their <code>parameters</code>.</p>

specializesFromLibrary('Performances::performances')
owningType <> null and
    (owningType.oclIsKindOf(Behavior) or
     owningType.oclIsKindOf(Step)) implies
    specializesFromLibrary('Performances::Performance::enclosedPerformance')
isComposite and owningType <> null and
(owningType.oclIsKindOf(Structure) or
 owningType.oclIsKindOf(Feature) and
 owningType.oclAsType(Feature).type->
    exists(oclIsKindOf(Structure)) implies
    specializesFromLibrary('Objects::Object::ownedPerformance')
owningType <> null and
    (owningType.oclIsKindOf(Behavior) or
     owningType.oclIsKindOf(Step)) and
    self.isComposite implies
    specializesFromLibrary('Performances::Performance::subperformance')
behavior = type->selectByKind(Behavior)"""
    behavior = EReference(ordered=True, unique=True, containment=False,
                          derived=True, upper=-1, transient=True, derived_class=DerivedBehavior)
    parameter = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedParameter)

    def __init__(self, *, behavior=None, parameter=None, **kwargs):

        super().__init__(**kwargs)

        if behavior:
            self.behavior.extend(behavior)

        if parameter:
            self.parameter.extend(parameter)


class DerivedDefinition(EDerivedCollection):
    pass


class DerivedDirectedusage(EDerivedCollection):
    pass


class DerivedNestedaction(EDerivedCollection):
    pass


class DerivedNestedallocation(EDerivedCollection):
    pass


class DerivedNestedanalysiscase(EDerivedCollection):
    pass


class DerivedNestedattribute(EDerivedCollection):
    pass


class DerivedNestedcalculation(EDerivedCollection):
    pass


class DerivedNestedcase(EDerivedCollection):
    pass


class DerivedNestedconcern(EDerivedCollection):
    pass


class DerivedNestedconnection(EDerivedCollection):
    pass


class DerivedNestedconstraint(EDerivedCollection):
    pass


class DerivedNestedenumeration(EDerivedCollection):
    pass


class DerivedNestedflow(EDerivedCollection):
    pass


class DerivedNestedinterface(EDerivedCollection):
    pass


class DerivedNesteditem(EDerivedCollection):
    pass


class DerivedNestedmetadata(EDerivedCollection):
    pass


class DerivedNestedoccurrence(EDerivedCollection):
    pass


class DerivedNestedpart(EDerivedCollection):
    pass


class DerivedNestedport(EDerivedCollection):
    pass


class DerivedNestedreference(EDerivedCollection):
    pass


class DerivedNestedrendering(EDerivedCollection):
    pass


class DerivedNestedrequirement(EDerivedCollection):
    pass


class DerivedNestedstate(EDerivedCollection):
    pass


class DerivedNestedtransition(EDerivedCollection):
    pass


class DerivedNestedusage(EDerivedCollection):
    pass


class DerivedNestedusecase(EDerivedCollection):
    pass


class DerivedNestedverificationcase(EDerivedCollection):
    pass


class DerivedNestedview(EDerivedCollection):
    pass


class DerivedNestedviewpoint(EDerivedCollection):
    pass


class DerivedUsage(EDerivedCollection):
    pass


class DerivedVariant(EDerivedCollection):
    pass


class DerivedVariantmembership(EDerivedCollection):
    pass


class Usage(Feature):
    """<p>A <code>Usage</code> is a usage of a <code>Definition</code>.</p>

<p>A <code>Usage</code> may have <code>nestedUsages</code> that model <code>features</code> that apply in the context of the <code>owningUsage</code>. A <code>Usage</code> may also have <code>Definitions</code> nested in it, but this has no semantic significance, other than the nested scoping resulting from the <code>Usage</code> being considered as a <code>Namespace</code> for any nested <code>Definitions</code>.</p>

<p>However, if a <code>Usage</code> has <code>isVariation = true</code>, then it represents a <em>variation point</em> <code>Usage</code>. In this case, all of its <code>members</code> must be <code>variant</code> <code>Usages</code>, related to the <code>Usage</code> by <code>VariantMembership</code> <code>Relationships</code>. Rather than being <code>features</code> of the <code>Usage</code>, <code>variant</code> <code>Usages</code> model different concrete alternatives that can be chosen to fill in for the variation point <code>Usage</code>.</p>
variant = variantMembership.ownedVariantUsage
variantMembership = ownedMembership->selectByKind(VariantMembership)
isVariation implies ownedFeatureMembership->isEmpty()
isReference = not isComposite
owningVariationUsage <> null implies
    specializes(owningVariationUsage)
isVariation implies
    not ownedSpecialization.specific->exists(
        oclIsKindOf(Definition) and
        oclAsType(Definition).isVariation or
        oclIsKindOf(Usage) and
        oclAsType(Usage).isVariation)
owningVariationDefinition <> null implies
    specializes(owningVariationDefinition)
directedUsage = directedFeature->selectByKind(Usage)
nestedAction = nestedUsage->selectByKind(ActionUsage)
nestedAllocation = nestedUsage->selectByKind(AllocationUsage)
nestedAnalysisCase = nestedUsage->selectByKind(AnalysisCaseUsage)
nestedAttribute = nestedUsage->selectByKind(AttributeUsage)
nestedCalculation = nestedUsage->selectByKind(CalculationUsage)
nestedCase = nestedUsage->selectByKind(CaseUsage)
nestedConcern = nestedUsage->selectByKind(ConcernUsage)
nestedConnection = nestedUsage->selectByKind(ConnectorAsUsage)
nestedConstraint = nestedUsage->selectByKind(ConstraintUsage)
ownedNested = nestedUsage->selectByKind(EnumerationUsage)
nestedFlow = nestedUsage->selectByKind(FlowUsage)
nestedInterface = nestedUsage->selectByKind(ReferenceUsage)
nestedItem = nestedUsage->selectByKind(ItemUsage)
nestedMetadata = nestedUsage->selectByKind(MetadataUsage)
nestedOccurrence = nestedUsage->selectByKind(OccurrenceUsage)
nestedPart = nestedUsage->selectByKind(PartUsage)
nestedPort = nestedUsage->selectByKind(PortUsage)
nestedReference = nestedUsage->selectByKind(ReferenceUsage)
nestedRendering = nestedUsage->selectByKind(RenderingUsage)
nestedRequirement = nestedUsage->selectByKind(RequirementUsage)
nestedState = nestedUsage->selectByKind(StateUsage)
nestedTransition = nestedUsage->selectByKind(TransitionUsage)
nestedUsage = ownedFeature->selectByKind(Usage)
nestedUseCase = nestedUsage->selectByKind(UseCaseUsage)
nestedVerificationCase = nestedUsage->selectByKind(VerificationCaseUsage)
nestedView = nestedUsage->selectByKind(ViewUsage)
nestedViewpoint = nestedUsage->selectByKind(ViewpointUsage)
usage = feature->selectByKind(Usage)
direction <> null or isEnd or featuringType->isEmpty() implies
    isReference
isVariation implies isAbstract
mayTimeVary =
    owningType <> null and
    owningType.specializesFromLibrary('Occurrences::Occurrence') and
    not (
        isPortion or
        specializesFromLibrary('Links::SelfLink') or
        specializesFromLibrary('Occurrences::HappensLink') or
        isComposite and specializesFromLibrary('Actions::Action')
    )
owningVariationUsage <> null implies
    featuringType->asSet() = owningVariationUsage.featuringType->asSet()"""
    _isReference = EAttribute(eType=EBoolean, unique=True, derived=True,
                              changeable=True, name='isReference', transient=True)
    isVariation = EAttribute(eType=EBoolean, unique=True, derived=False, changeable=True)
    _mayTimeVary = EAttribute(eType=EBoolean, unique=True, derived=True,
                              changeable=True, name='mayTimeVary', transient=True)
    definition = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedDefinition)
    directedUsage = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedDirectedusage)
    nestedAction = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedNestedaction)
    nestedAllocation = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedNestedallocation)
    nestedAnalysisCase = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedNestedanalysiscase)
    nestedAttribute = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedNestedattribute)
    nestedCalculation = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedNestedcalculation)
    nestedCase = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNestedcase)
    nestedConcern = EReference(ordered=False, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedNestedconcern)
    nestedConnection = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedNestedconnection)
    nestedConstraint = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedNestedconstraint)
    nestedEnumeration = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedNestedenumeration)
    nestedFlow = EReference(ordered=False, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNestedflow)
    nestedInterface = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedNestedinterface)
    nestedItem = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNesteditem)
    nestedMetadata = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedNestedmetadata)
    nestedOccurrence = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedNestedoccurrence)
    nestedPart = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNestedpart)
    nestedPort = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNestedport)
    nestedReference = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedNestedreference)
    nestedRendering = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedNestedrendering)
    nestedRequirement = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedNestedrequirement)
    nestedState = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedNestedstate)
    nestedTransition = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedNestedtransition)
    nestedUsage = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedNestedusage)
    nestedUseCase = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedNestedusecase)
    nestedVerificationCase = EReference(ordered=True, unique=True, containment=False,
                                        derived=True, upper=-1, transient=True, derived_class=DerivedNestedverificationcase)
    nestedView = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedNestedview)
    nestedViewpoint = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedNestedviewpoint)
    _owningDefinition = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='owningDefinition', transient=True)
    _owningUsage = EReference(ordered=False, unique=True, containment=False,
                              derived=True, name='owningUsage', transient=True)
    usage = EReference(ordered=True, unique=True, containment=False, derived=True,
                       upper=-1, transient=True, derived_class=DerivedUsage)
    variant = EReference(ordered=False, unique=True, containment=False,
                         derived=True, upper=-1, transient=True, derived_class=DerivedVariant)
    variantMembership = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedVariantmembership)

    @property
    def isReference(self):
        raise NotImplementedError('Missing implementation for isReference')

    @isReference.setter
    def isReference(self, value):
        raise NotImplementedError('Missing implementation for isReference')

    @property
    def mayTimeVary(self):
        raise NotImplementedError('Missing implementation for mayTimeVary')

    @mayTimeVary.setter
    def mayTimeVary(self, value):
        raise NotImplementedError('Missing implementation for mayTimeVary')

    @property
    def owningDefinition(self):
        raise NotImplementedError('Missing implementation for owningDefinition')

    @owningDefinition.setter
    def owningDefinition(self, value):
        raise NotImplementedError('Missing implementation for owningDefinition')

    @property
    def owningUsage(self):
        raise NotImplementedError('Missing implementation for owningUsage')

    @owningUsage.setter
    def owningUsage(self, value):
        raise NotImplementedError('Missing implementation for owningUsage')

    def __init__(self, *, definition=None, directedUsage=None, isReference=None, isVariation=None, mayTimeVary=None, nestedAction=None, nestedAllocation=None, nestedAnalysisCase=None, nestedAttribute=None, nestedCalculation=None, nestedCase=None, nestedConcern=None, nestedConnection=None, nestedConstraint=None, nestedEnumeration=None, nestedFlow=None, nestedInterface=None, nestedItem=None, nestedMetadata=None, nestedOccurrence=None, nestedPart=None, nestedPort=None, nestedReference=None, nestedRendering=None, nestedRequirement=None, nestedState=None, nestedTransition=None, nestedUsage=None, nestedUseCase=None, nestedVerificationCase=None, nestedView=None, nestedViewpoint=None, owningDefinition=None, owningUsage=None, usage=None, variant=None, variantMembership=None, **kwargs):

        super().__init__(**kwargs)

        if isReference is not None:
            self.isReference = isReference

        if isVariation is not None:
            self.isVariation = isVariation

        if mayTimeVary is not None:
            self.mayTimeVary = mayTimeVary

        if definition:
            self.definition.extend(definition)

        if directedUsage:
            self.directedUsage.extend(directedUsage)

        if nestedAction:
            self.nestedAction.extend(nestedAction)

        if nestedAllocation:
            self.nestedAllocation.extend(nestedAllocation)

        if nestedAnalysisCase:
            self.nestedAnalysisCase.extend(nestedAnalysisCase)

        if nestedAttribute:
            self.nestedAttribute.extend(nestedAttribute)

        if nestedCalculation:
            self.nestedCalculation.extend(nestedCalculation)

        if nestedCase:
            self.nestedCase.extend(nestedCase)

        if nestedConcern:
            self.nestedConcern.extend(nestedConcern)

        if nestedConnection:
            self.nestedConnection.extend(nestedConnection)

        if nestedConstraint:
            self.nestedConstraint.extend(nestedConstraint)

        if nestedEnumeration:
            self.nestedEnumeration.extend(nestedEnumeration)

        if nestedFlow:
            self.nestedFlow.extend(nestedFlow)

        if nestedInterface:
            self.nestedInterface.extend(nestedInterface)

        if nestedItem:
            self.nestedItem.extend(nestedItem)

        if nestedMetadata:
            self.nestedMetadata.extend(nestedMetadata)

        if nestedOccurrence:
            self.nestedOccurrence.extend(nestedOccurrence)

        if nestedPart:
            self.nestedPart.extend(nestedPart)

        if nestedPort:
            self.nestedPort.extend(nestedPort)

        if nestedReference:
            self.nestedReference.extend(nestedReference)

        if nestedRendering:
            self.nestedRendering.extend(nestedRendering)

        if nestedRequirement:
            self.nestedRequirement.extend(nestedRequirement)

        if nestedState:
            self.nestedState.extend(nestedState)

        if nestedTransition:
            self.nestedTransition.extend(nestedTransition)

        if nestedUsage:
            self.nestedUsage.extend(nestedUsage)

        if nestedUseCase:
            self.nestedUseCase.extend(nestedUseCase)

        if nestedVerificationCase:
            self.nestedVerificationCase.extend(nestedVerificationCase)

        if nestedView:
            self.nestedView.extend(nestedView)

        if nestedViewpoint:
            self.nestedViewpoint.extend(nestedViewpoint)

        if owningDefinition is not None:
            self.owningDefinition = owningDefinition

        if owningUsage is not None:
            self.owningUsage = owningUsage

        if usage:
            self.usage.extend(usage)

        if variant:
            self.variant.extend(variant)

        if variantMembership:
            self.variantMembership.extend(variantMembership)

    def referencedFeatureTarget(self):
        """<p>If <code>ownedReferenceSubsetting</code> is not null, return the <code>featureTarget</code> of the <code>referencedFeature</code> of the <code>ownedReferenceSubsetting</code>.</p>
if ownedReferenceSubsetting = null then null
else ownedReferenceSubsetting.referencedFeature.featureTarget
endif"""
        raise NotImplementedError('operation referencedFeatureTarget(...) not yet implemented')


class VariantMembership(OwningMembership):
    """<p>A <code>VariantMembership</code> is a <code>Membership</code> between a variation point <code>Definition</code> or <code>Usage</code> and a <code>Usage</code> that represents a variant in the context of that variation. The <code>membershipOwningNamespace</code> for the <code>VariantMembership</code> must be either a Definition or a <code>Usage</code> with <code>isVariation = true</code>.</p>
membershipOwningNamespace.oclIsKindOf(Definition) and
    membershipOwningNamespace.oclAsType(Definition).isVariation or
membershipOwningNamespace.oclIsKindOf(Usage) and
    membershipOwningNamespace.oclAsType(Usage).isVariation
"""
    _ownedVariantUsage = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedVariantUsage', transient=True)

    @property
    def ownedVariantUsage(self):
        raise NotImplementedError('Missing implementation for ownedVariantUsage')

    @ownedVariantUsage.setter
    def ownedVariantUsage(self, value):
        raise NotImplementedError('Missing implementation for ownedVariantUsage')

    def __init__(self, *, ownedVariantUsage=None, **kwargs):

        super().__init__(**kwargs)

        if ownedVariantUsage is not None:
            self.ownedVariantUsage = ownedVariantUsage


class DerivedAssociationend(EDerivedCollection):
    pass


class DerivedRelatedtype(EDerivedCollection):
    pass


class DerivedTargettype(EDerivedCollection):
    pass


class Association(Classifier, Relationship):
    """<p>An <code>Association</code> is a <code>Relationship</code> and a <code>Classifier</code> to enable classification of links between things (in the universe). The co-domains (<code>types</code>) of the <code>associationEnd</code> <code>Features</code> are the <code>relatedTypes</code>, as co-domain and participants (linked things) of an <code>Association</code> identify each other.</p>

relatedType = associationEnd.type
specializesFromLibrary('Links::Link')
oclIsKindOf(Structure) = oclIsKindOf(AssociationStructure)
associationEnd->size() = 2 implies
    specializesFromLibrary('Links::BinaryLink')
not isAbstract implies relatedType->size() >= 2
associationEnds->size() > 2 implies
    not specializesFromLibrary('Links::BinaryLink')
sourceType =
    if relatedType->isEmpty() then null
    else relatedType->first() endif
targetType =
    if relatedType->size() < 2 then OrderedSet{}
    else 
        relatedType->
            subSequence(2, relatedType->size())->
            asOrderedSet() 
    endif
ownedEndFeature->forAll(type->size() = 1)"""
    associationEnd = EReference(ordered=False, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedAssociationend)
    relatedType = EReference(ordered=True, unique=False, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedRelatedtype)
    _sourceType = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='sourceType', transient=True)
    targetType = EReference(ordered=False, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedTargettype)

    @property
    def sourceType(self):
        raise NotImplementedError('Missing implementation for sourceType')

    @sourceType.setter
    def sourceType(self, value):
        raise NotImplementedError('Missing implementation for sourceType')

    def __init__(self, *, associationEnd=None, relatedType=None, sourceType=None, targetType=None, **kwargs):

        super().__init__(**kwargs)

        if associationEnd:
            self.associationEnd.extend(associationEnd)

        if relatedType:
            self.relatedType.extend(relatedType)

        if sourceType is not None:
            self.sourceType = sourceType

        if targetType:
            self.targetType.extend(targetType)


class DerivedAttributedefinition(EDerivedCollection):
    pass


class AttributeUsage(Usage):
    """<p>An <code>AttributeUsage</code> is a <code>Usage</code> whose type is a <code>DataType</code>. Nominally, if the type is an <code>AttributeDefinition</code>, an <code>AttributeUsage</code> is a usage of a <code>AttributeDefinition</code> to represent the value of some system quality or characteristic. However, other kinds of kernel <code>DataTypes</code> are also allowed, to permit use of <code>DataTypes</code> from the Kernel Model Libraries. An <code>AttributeUsage</code> itself as well as all its nested <code>features</code> must be referential (non-composite).</p>

<p>An <code>AttributeUsage</code> must specialize, directly or indirectly, the base <code>Feature</code> <code><em>Base::dataValues</em></code> from the Kernel Semantic Library.</p>
isReference
feature->forAll(not isComposite)
specializesFromLibrary('Base::dataValues')"""
    attributeDefinition = EReference(ordered=True, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedAttributedefinition)

    def __init__(self, *, attributeDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if attributeDefinition:
            self.attributeDefinition.extend(attributeDefinition)


class DerivedParameter(EDerivedCollection):
    pass


class DerivedStep(EDerivedCollection):
    pass


class Behavior(Class):
    """<p>A <code>Behavior </code>coordinates occurrences of other <code>Behaviors</code>, as well as changes in objects. <code>Behaviors</code> can be decomposed into <code>Steps</code> and be characterized by <code>parameters</code>.</p>

ownedSpecialization.general->forAll(not oclIsKindOf(Structure))
specializesFromLibrary('Performances::Performance')
step = feature->selectByKind(Step)"""
    parameter = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedParameter)
    step = EReference(ordered=False, unique=True, containment=False, derived=True,
                      upper=-1, transient=True, derived_class=DerivedStep)

    def __init__(self, *, parameter=None, step=None, **kwargs):

        super().__init__(**kwargs)

        if parameter:
            self.parameter.extend(parameter)

        if step:
            self.step.extend(step)


class DerivedAssociation(EDerivedCollection):
    pass


class DerivedConnectorend(EDerivedCollection):
    pass


class DerivedRelatedfeature(EDerivedCollection):
    pass


class DerivedTargetfeature(EDerivedCollection):
    pass


class Connector(Feature, Relationship):
    """<p>A <code>Connector</code> is a usage of <code>Associations</code>, with links restricted according to instances of the <code>Type</code> in which they are used (domain of the <code>Connector</code>). The <code>associations</code> of the <code>Connector</code> restrict what kinds of things might be linked. The <code>Connector</code> further restricts these links to be between values of <code>Features</code> on instances of its domain.</p>

relatedFeature = connectorEnd.ownedReferenceSubsetting->
    select(s | s <> null).subsettedFeature
relatedFeature->forAll(f | 
    if featuringType->isEmpty() then f.isFeaturedWithin(null)
    else featuringType->forAll(t | f.isFeaturedWithin(t))
    endif)
sourceFeature = 
    if relatedFeature->isEmpty() then null 
    else relatedFeature->first() 
    endif
targetFeature =
    if relatedFeature->size() < 2 then OrderedSet{}
    else 
        relatedFeature->
            subSequence(2, relatedFeature->size())->
            asOrderedSet()
    endif
not isAbstract implies relatedFeature->size() >= 2
specializesFromLibrary('Links::links')
association->exists(oclIsKindOf(AssociationStructure)) implies
    specializesFromLibrary('Objects::linkObjects')
connectorEnds->size() = 2 and
association->exists(oclIsKindOf(AssociationStructure)) implies
    specializesFromLibrary('Objects::binaryLinkObjects')
connectorEnd->size() = 2 implies
    specializesFromLibrary('Links::binaryLinks')
connectorEnds->size() > 2 implies
    not specializesFromLibrary('Links::BinaryLink')
let commonFeaturingTypes : OrderedSet(Type) = 
    relatedFeature->closure(featuringType)->select(t | 
        relatedFeature->forAll(f | f.isFeaturedWithin(t))
    ) in
let nearestCommonFeaturingTypes : OrderedSet(Type) =
    commonFeaturingTypes->reject(t1 | 
        commonFeaturingTypes->exists(t2 | 
            t2 <> t1 and t2->closure(featuringType)->contains(t1)
    )) in
if nearestCommonFeaturingTypes->isEmpty() then null
else nearestCommonFeaturingTypes->first()
endif"""
    association = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedAssociation)
    connectorEnd = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedConnectorend)
    _defaultFeaturingType = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='defaultFeaturingType', transient=True)
    relatedFeature = EReference(ordered=True, unique=False, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedRelatedfeature)
    _sourceFeature = EReference(ordered=True, unique=True, containment=False,
                                derived=True, name='sourceFeature', transient=True)
    targetFeature = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedTargetfeature)

    @property
    def defaultFeaturingType(self):
        raise NotImplementedError('Missing implementation for defaultFeaturingType')

    @defaultFeaturingType.setter
    def defaultFeaturingType(self, value):
        raise NotImplementedError('Missing implementation for defaultFeaturingType')

    @property
    def sourceFeature(self):
        raise NotImplementedError('Missing implementation for sourceFeature')

    @sourceFeature.setter
    def sourceFeature(self, value):
        raise NotImplementedError('Missing implementation for sourceFeature')

    def __init__(self, *, association=None, connectorEnd=None, defaultFeaturingType=None, relatedFeature=None, sourceFeature=None, targetFeature=None, **kwargs):

        super().__init__(**kwargs)

        if association:
            self.association.extend(association)

        if connectorEnd:
            self.connectorEnd.extend(connectorEnd)

        if defaultFeaturingType is not None:
            self.defaultFeaturingType = defaultFeaturingType

        if relatedFeature:
            self.relatedFeature.extend(relatedFeature)

        if sourceFeature is not None:
            self.sourceFeature = sourceFeature

        if targetFeature:
            self.targetFeature.extend(targetFeature)


class EndFeatureMembership(FeatureMembership):
    """<p><code>EndFeatureMembership</code> is a <code>FeatureMembership</code> that requires its <code>memberFeature</code> be owned and have <code>isEnd = true</code>.</p>

ownedMemberFeature.isEnd"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class Expression(Step):
    """<p>An <code>Expression</code> is a <code>Step</code> that is typed by a <code>Function</code>. An <code>Expression</code> that also has a <code>Function</code> as its <code>featuringType</code> is a computational step within that <code>Function</code>. An <code>Expression</code> always has a single <code>result</code> parameter, which redefines the <code>result</code> parameter of its defining <code>function</code>. This allows <code>Expressions</code> to be interconnected in tree structures, in which inputs to each <code>Expression</code> in the tree are determined as the results of other <code>Expression</code> in the tree.</p>

isModelLevelEvaluable = modelLevelEvaluable(Set(Element){})
specializesFromLibrary('Performances::evaluations')
owningMembership <> null and 
owningMembership.oclIsKindOf(FeatureValue) implies
    let featureWithValue : Feature = 
        owningMembership.oclAsType(FeatureValue).featureWithValue in
    featuringType = featureWithValue.featuringType
ownedMembership.selectByKind(ResultExpressionMembership)->
    forAll(mem | ownedFeature.selectByKind(BindingConnector)->
        exists(binding |
            binding.relatedFeature->includes(result) and
            binding.relatedFeature->includes(mem.ownedResultExpression.result)))
result =
    let resultParams : Sequence(Feature) =
        featureMemberships->
            selectByKind(ReturnParameterMembership).
            ownedMemberParameter in
    if resultParams->notEmpty() then resultParams->first()
    else null
    endif

featureMembership->
    selectByKind(ReturnParameterMembership)->
    size() = 1
membership->selectByKind(ResultExpressionMembership)->size() <= 1"""
    _isModelLevelEvaluable = EAttribute(
        eType=EBoolean, unique=True, derived=True, changeable=True, name='isModelLevelEvaluable', transient=True)
    _function = EReference(ordered=False, unique=True, containment=False,
                           derived=True, name='function', transient=True)
    _result = EReference(ordered=False, unique=True, containment=False,
                         derived=True, name='result', transient=True)

    @property
    def function(self):
        raise NotImplementedError('Missing implementation for function')

    @function.setter
    def function(self, value):
        raise NotImplementedError('Missing implementation for function')

    @property
    def isModelLevelEvaluable(self):
        raise NotImplementedError('Missing implementation for isModelLevelEvaluable')

    @isModelLevelEvaluable.setter
    def isModelLevelEvaluable(self, value):
        raise NotImplementedError('Missing implementation for isModelLevelEvaluable')

    @property
    def result(self):
        raise NotImplementedError('Missing implementation for result')

    @result.setter
    def result(self, value):
        raise NotImplementedError('Missing implementation for result')

    def __init__(self, *, function=None, isModelLevelEvaluable=None, result=None, **kwargs):

        super().__init__(**kwargs)

        if isModelLevelEvaluable is not None:
            self.isModelLevelEvaluable = isModelLevelEvaluable

        if function is not None:
            self.function = function

        if result is not None:
            self.result = result

    def checkCondition(self, target=None):
        """<p>Model-level evaluate this <code>Expression</code> with the given <code>target</code>. If the result is a <code>LiteralBoolean</code>, return its <code>value</code>. Otherwise return <code>false</code>.</p>

let results: Sequence(Element) = evaluate(target) in
    result->size() = 1 and
    results->first().oclIsKindOf(LiteralBoolean) and 
    results->first().oclAsType(LiteralBoolean).value"""
        raise NotImplementedError('operation checkCondition(...) not yet implemented')

    def evaluate(self, target=None):
        """<p>If this <code>Expression</code> <code>isModelLevelEvaluable</code>, then evaluate it using the <code>target</code> as the context <code>Element</code> for resolving <code>Feature</code> names and testing classification. The result is a collection of <code>Elements</code>, which, for a fully evaluable <code>Expression</code>, will be a <code>LiteralExpression</code> or a <code>Feature</code> that is not an <code>Expression</code>.</p>
isModelLevelEvaluable
let resultExprs : Sequence(Expression) =
    ownedFeatureMembership->
        selectByKind(ResultExpressionMembership).
        ownedResultExpression in
if resultExpr->isEmpty() then Sequence{}
else resultExprs->first().evaluate(target)
endif"""
        raise NotImplementedError('operation evaluate(...) not yet implemented')

    def modelLevelEvaluable(self, visited=None):
        """<p>Return whether this <code>Expression</code> is model-level evaluable. The <code>visited</code> parameter is used to track possible circular <code>Feature</code> references made from <code>FeatureReferenceExpressions</code> (see the redefinition of this operation for <code>FeatureReferenceExpression</code>). Such circular references are not allowed in model-level evaluable expressions.</p>

<p>An <code>Expression</code> that is not otherwise specialized is model-level evaluable if it has no (non-implied) <code>ownedSpecializations</code> and all its <code>ownedFeatures</code> are either <code>in</code> parameters, the <code>result</code> <code>parameter</code> or a result <code>Expression</code> owned via a <code>ResultExpressionMembership</code>. The <code>parameters</code>  must not have any <code>ownedFeatures</code> or a <code>FeatureValue</code>, and the result <code>Expression</code> must be model-level evaluable.</p>
ownedSpecialization->forAll(isImplied) and 
ownedFeature->forAll(f |
    (directionOf(f) = FeatureDirectionKind::_'in' or f = result) and
        f.ownedFeature->isEmpty() and f.valuation = null or
    f.owningFeatureMembership.oclIsKindOf(ResultExpressionMembership) and
        f.oclAsType(Expression).modelLevelEvaluable(visited)
    """
        raise NotImplementedError('operation modelLevelEvaluable(...) not yet implemented')


class MembershipExpose(MembershipImport, Expose):
    """<p>A <code>MembershipExpose</code> is an <code>Expose</code> <code.Relationship</code> that exposes a specific <code>importedMembership</code> and, if <code>isRecursive = true</code>, additional <code>Memberships</code> recursively.</p>"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class MetadataFeature(Feature, AnnotatingElement):
    """<p>A <code>MetadataFeature</code> is a <code>Feature</code> that is an <code>AnnotatingElement</code> used to annotate another <code>Element</code> with metadata. It is typed by a <code>Metaclass</code>. All its <code>ownedFeatures</code> must redefine <code>features</code> of its <code>metaclass</code> and any feature bindings must be model-level evaluable.</p>


type->selectByKind(Metaclass).size() = 1
not metaclass.isAbstract
specializesFromLibrary('Metaobjects::metaobjects')
ownedFeature->closure(ownedFeature)->forAll(f |
    f.declaredName = null and f.declaredShortName = null and
    f.valuation <> null implies f.valuation.value.isModelLevelEvaluable and
    f.redefinition.redefinedFeature->size() = 1)
metaclass = 
    let metaclassTypes : Sequence(Type) = type->selectByKind(Metaclass) in
    if metaclassTypes->isEmpty() then null
    else metaClassTypes->first()
    endif
let baseAnnotatedElementFeature : Feature =
    resolveGlobal('Metaobjects::Metaobject::annotatedElement').memberElement.
    oclAsType(Feature) in
let annotatedElementFeatures : OrderedSet(Feature) = feature->
    select(specializes(baseAnnotatedElementFeature))->
    excluding(baseAnnotatedElementFeature) in
annotatedElementFeatures->notEmpty() implies
    let annotatedElementTypes : Set(Feature) =
        annotatedElementFeatures.typing.type->asSet() in
    let metaclasses : Set(Metaclass) =
        annotatedElement.oclType().qualifiedName->collect(qn | 
            resolveGlobal(qn).memberElement.oclAsType(Metaclass)) in
   metaclasses->forAll(m | annotatedElementTypes->exists(t | m.specializes(t)))
isSemantic() implies
    let annotatedTypes : Sequence(Type) = 
        annotatedElement->selectAsKind(Type) in
    let baseTypes : Sequence(MetadataFeature) = 
        evaluateFeature(resolveGlobal(
            'Metaobjects::SemanticMetadata::baseType').
            memberElement.
            oclAsType(Feature))->
        selectAsKind(MetadataFeature) in
    annotatedTypes->notEmpty() and 
    baseTypes()->notEmpty() and 
    baseTypes()->first().isSyntactic() implies
        let annotatedType : Type = annotatedTypes->first() in
        let baseType : Element = baseTypes->first().syntaxElement() in
        if annotatedType.oclIsKindOf(Classifier) and 
            baseType.oclIsKindOf(Feature) then
            baseType.oclAsType(Feature).type->
                forAll(t | annotatedType.specializes(t))
        else if baseType.oclIsKindOf(Type) then
            annotatedType.specializes(baseType.oclAsType(Type))
        else
            true
        endif"""
    _metaclass = EReference(ordered=False, unique=True, containment=False,
                            derived=True, name='metaclass', transient=True)

    @property
    def metaclass(self):
        raise NotImplementedError('Missing implementation for metaclass')

    @metaclass.setter
    def metaclass(self, value):
        raise NotImplementedError('Missing implementation for metaclass')

    def __init__(self, *, metaclass=None, **kwargs):

        super().__init__(**kwargs)

        if metaclass is not None:
            self.metaclass = metaclass

    def evaluateFeature(self, baseFeature=None):
        """<p>If the given <code>baseFeature</code> is a <code>feature</code> of this <code>MetadataFeature</code>, or is directly or indirectly redefined by a <code>feature</code>, then return the result of evaluating the appropriate (model-level evaluable) <code>value</code> <code>Expression</code> for it (if any), with the <code>MetadataFeature</code> as the target.</p>
let selectedFeatures : Sequence(Feature) = feature->
    select(closure(ownedRedefinition.redefinedFeature)->
           includes(baseFeature)) in
if selectedFeatures->isEmpty() then null
else
    let selectedFeature : Feature = selectedFeatures->first() in
    let featureValues : FeatureValue = selectedFeature->
        closure(ownedRedefinition.redefinedFeature).ownedMember->
        selectAsKind(FeatureValue) in
    if featureValues->isEmpty() then null
    else featureValues->first().value.evaluate(self)
    endif"""
        raise NotImplementedError('operation evaluateFeature(...) not yet implemented')

    def isSemantic(self):
        """<p>Check if this <code>MetadataFeature</code> has a <code>metaclass</code> which is a kind of <code><em>SemanticMetadata</code>.<p>
specializesFromLibrary('Metaobjects::SemanticMetadata')"""
        raise NotImplementedError('operation isSemantic(...) not yet implemented')

    def isSyntactic(self):
        """<p>Check if this <code>MetadataFeature</code> has a <code>metaclass</code> that is a kind of <code><em>KerML::Element</em></code> (that is, it is from the reflective abstract syntax model).</p>
specializesFromLibrary('KerML::Element')"""
        raise NotImplementedError('operation isSyntactic(...) not yet implemented')

    def syntaxElement(self):
        """<p>If this <code>MetadataFeature</code> reflectively represents a model element, then return the corresponding <code>Element</code> instance from the MOF abstract syntax representation of the model.</p>
No OCL
isSyntactic()"""
        raise NotImplementedError('operation syntaxElement(...) not yet implemented')


class DerivedBound(EDerivedCollection):
    pass


class MultiplicityRange(Multiplicity):
    """<p>A <code>MultiplicityRange</code> is a <code>Multiplicity</code> whose value is defined to be the (inclusive) range of natural numbers given by the result of a <code>lowerBound</code> <code>Expression</code> and the result of an <code>upperBound</code> <code>Expression</code>. The result of these <code>Expressions</code> shall be of type <code><em>Natural</em></code>. If the result of the <code>upperBound</code> <code>Expression</code> is the unbounded value <code>*</code>, then the specified range includes all natural numbers greater than or equal to the <code>lowerBound</code> value. If no <code>lowerBound</code> <code>Expression</code>, then the default is that the lower bound has the same value as the upper bound, except if the <code>upperBound</code> evaluates to <code>*</code>, in which case the default for the lower bound is 0.</p>

bound->forAll(b | b.featuringType = self.featuringType)
bound->forAll(b |
    b.result.specializesFromLibrary('ScalarValues::Integer') and
    let value : UnlimitedNatural = valueOf(b) in
    value <> null implies value >= 0
)
lowerBound =
    let ownedExpressions : Sequence(Expression) =
        ownedMember->selectByKind(Expression) in
    if ownedExpressions->size() < 2 then null
    else ownedExpressions->first()
    endif
upperBound =
    let ownedExpressions : Sequence(Expression) =
        ownedMember->selectByKind(Expression) in
    if ownedExpressions->isEmpty() then null
    else if ownedExpressions->size() = 1 then ownedExpressions->at(1)
    else ownedExpressions->at(2)
    endif endif 
bound =
    if upperBound = null then Sequence{}
    else if lowerBound = null then Sequence{upperBound}
    else Sequence{lowerBound, upperBound}
    endif endif
if lowerBound = null then
    ownedMember->notEmpty() and
    ownedMember->at(1) = upperBound
else
    ownedMember->size() > 1 and
    ownedMember->at(1) = lowerBound and
    ownedMember->at(2) = upperBound
endif"""
    bound = EReference(ordered=True, unique=True, containment=False, derived=True,
                       upper=-1, transient=True, derived_class=DerivedBound)
    _lowerBound = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='lowerBound', transient=True)
    _upperBound = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='upperBound', transient=True)

    @property
    def lowerBound(self):
        raise NotImplementedError('Missing implementation for lowerBound')

    @lowerBound.setter
    def lowerBound(self, value):
        raise NotImplementedError('Missing implementation for lowerBound')

    @property
    def upperBound(self):
        raise NotImplementedError('Missing implementation for upperBound')

    @upperBound.setter
    def upperBound(self, value):
        raise NotImplementedError('Missing implementation for upperBound')

    def __init__(self, *, bound=None, lowerBound=None, upperBound=None, **kwargs):

        super().__init__(**kwargs)

        if bound:
            self.bound.extend(bound)

        if lowerBound is not None:
            self.lowerBound = lowerBound

        if upperBound is not None:
            self.upperBound = upperBound

    def hasBounds(self, lower=None, upper=None):
        """<p>Check whether this <code>MultiplicityRange</code> represents the range bounded by the given values <code>lower</code> and <code>upper</code>, presuming the <code>lowerBound</code> and <code>upperBound</code> <code>Expressions</code> are model-level evaluable.</p>
valueOf(upperBound) = upper and
let lowerValue: UnlimitedNatural = valueOf(lowerBound) in
(lowerValue = lower or
 lowerValue = null and 
    (lower = upper or 
     lower = 0 and upper = *))
 """
        raise NotImplementedError('operation hasBounds(...) not yet implemented')

    def valueOf(self, bound=None):
        """<p>Evaluate the given <code>bound</code> <code>Expression</code> (at model level) and return the result represented as a MOF <code>UnlimitedNatural</code> value.</p>
if bound = null or not bound.isModelLevelEvaluable then 
    null
else
    let boundEval: Sequence(Element) = bound.evaluate(owningType) in
    if boundEval->size() <> 1 then null else
        let valueEval: Element = boundEval->at(1) in
        if valueEval.oclIsKindOf(LiteralInfinity) then *
        else if valueEval.oclIsKindOf(LiteralInteger) then
            let value : Integer = 
                valueEval.oclAsKindOf(LiteralInteger).value in
            if value >= 0 then value else null endif
        else null
        endif endif
    endif
endif """
        raise NotImplementedError('operation valueOf(...) not yet implemented')


class NamespaceExpose(NamespaceImport, Expose):
    """<p>A <code>NamespaceExpose</code> is an <code>Expose</code> <code>Relationship</code> that exposes the <code>Memberships</code> of a specific <code>importedNamespace</code> and, if <code>isRecursive = true</code>, additional <code>Memberships</code> recursively.</p>"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class ObjectiveMembership(FeatureMembership):
    """<p>An <code>ObjectiveMembership</code> is a <code>FeatureMembership</code> that indicates that its <code>ownedObjectiveRequirement</code> is the objective <code>RequirementUsage</code> for its <code>owningType</code>, which must be a <code>CaseDefinition</code> or <code>CaseUsage</code>.</p>
owningType.oclIsType(CaseDefinition) or
owningType.oclIsType(CaseUsage)

ownedObjectiveRequirement.isComposite"""
    _ownedObjectiveRequirement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedObjectiveRequirement', transient=True)

    @property
    def ownedObjectiveRequirement(self):
        raise NotImplementedError('Missing implementation for ownedObjectiveRequirement')

    @ownedObjectiveRequirement.setter
    def ownedObjectiveRequirement(self, value):
        raise NotImplementedError('Missing implementation for ownedObjectiveRequirement')

    def __init__(self, *, ownedObjectiveRequirement=None, **kwargs):

        super().__init__(**kwargs)

        if ownedObjectiveRequirement is not None:
            self.ownedObjectiveRequirement = ownedObjectiveRequirement


class DerivedOccurrencedefinition(EDerivedCollection):
    pass


class OccurrenceUsage(Usage):
    """<p>An <code>OccurrenceUsage</code> is a <code>Usage</code> whose <code>types</code> are all <code>Classes</code>. Nominally, if a <code>type</code> is an <code>OccurrenceDefinition</code>, an <code>OccurrenceUsage</code> is a <code>Usage</code> of that <code>OccurrenceDefinition</code> within a system. However, other types of Kernel <code>Classes</code> are also allowed, to permit use of <code>Classes</code> from the Kernel Model Libraries.</p>

individualDefinition =
    let individualDefinitions : OrderedSet(OccurrenceDefinition) = 
        occurrenceDefinition->
            selectByKind(OccurrenceDefinition)->
            select(isIndividual) in
    if individualDefinitions->isEmpty() then null
    else individualDefinitions->first() endif
isIndividual implies individualDefinition <> null
specializesFromLibrary('Occurrences::occurrences')
isComposite and
owningType <> null and
(owningType.oclIsKindOf(Class) or
 owningType.oclIsKindOf(OccurrenceUsage) or
 owningType.oclIsKindOf(Feature) and
    owningType.oclAsType(Feature).type->
        exists(oclIsKind(Class))) implies
    specializesFromLibrary('Occurrences::Occurrence::suboccurrences')
occurrenceDefinition->
    selectByKind(OccurrenceDefinition)->
    select(isIndividual).size() <= 1
portionKind = PortionKind::snapshot implies
    specializesFromLibrary('Occurrences::Occurrence::snapshots')
portionKind = PortionKind::timeslice implies 
    specializesFromLibrary('Occurrences::Occurrence::timeSlices')
portionKind <> null implies
    owningType <> null and
    (owningType.oclIsKindOf(OccurrenceDefinition) or
     owningType.oclIsKindOf(OccurrenceUsage))
portionKind <> null implies isPortion"""
    isIndividual = EAttribute(eType=EBoolean, unique=True, derived=False,
                              changeable=True, default_value=False)
    portionKind = EAttribute(eType=PortionKind, unique=True, derived=False, changeable=True)
    _individualDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='individualDefinition', transient=True)
    occurrenceDefinition = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedOccurrencedefinition)

    @property
    def individualDefinition(self):
        raise NotImplementedError('Missing implementation for individualDefinition')

    @individualDefinition.setter
    def individualDefinition(self, value):
        raise NotImplementedError('Missing implementation for individualDefinition')

    def __init__(self, *, individualDefinition=None, isIndividual=None, occurrenceDefinition=None, portionKind=None, **kwargs):

        super().__init__(**kwargs)

        if isIndividual is not None:
            self.isIndividual = isIndividual

        if portionKind is not None:
            self.portionKind = portionKind

        if individualDefinition is not None:
            self.individualDefinition = individualDefinition

        if occurrenceDefinition:
            self.occurrenceDefinition.extend(occurrenceDefinition)


class ParameterMembership(FeatureMembership):
    """<p>A <code>ParameterMembership</code> is a <code>FeatureMembership</code> that identifies its <code>memberFeature</code> as a parameter, which is always owned, and must have a <code>direction</code>. A <code>ParameterMembership</code> must be owned by a <code>Behavior</code>, a <code>Step</code>, or the <code>result</code> parameter of a <code>ConstructorExpression</code>.</p>
ownedMemberParameter.direction = parameterDirection()
owningType.oclIsKindOf(Behavior) or owningType.oclIsKindOf(Step) or
owningType.owningMembership.oclIsKindOf(ReturnParameterMembership) and
    owningType.owningNamespace.oclIsKindOf(ConstructorExpression)"""
    _ownedMemberParameter = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedMemberParameter', transient=True)

    @property
    def ownedMemberParameter(self):
        raise NotImplementedError('Missing implementation for ownedMemberParameter')

    @ownedMemberParameter.setter
    def ownedMemberParameter(self, value):
        raise NotImplementedError('Missing implementation for ownedMemberParameter')

    def __init__(self, *, ownedMemberParameter=None, **kwargs):

        super().__init__(**kwargs)

        if ownedMemberParameter is not None:
            self.ownedMemberParameter = ownedMemberParameter

    def parameterDirection(self):
        """<p>Return the required value of the <code>direction</code> of the <code>ownedMemberParameter</code>. By default, this is <code>in</code>.</p>
FeatureDirectionKind::_'in'"""
        raise NotImplementedError('operation parameterDirection(...) not yet implemented')


class ReferenceUsage(Usage):
    """<p>A <code>ReferenceUsage</code> is a <code>Usage</code> that specifies a non-compositional (<code>isComposite = false</code>) reference to something. The <code>definition</code> of a <code>ReferenceUsage</code> can be any kind of <code>Classifier</code>, with the default being the top-level <code>Classifier</code> <code><em>Base::Anything</em></code> from the Kernel Semantic Library. This allows the specification of a generic reference without distinguishing if the thing referenced is an attribute value, item, action, etc.</p>
isReference"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class RequirementConstraintMembership(FeatureMembership):
    """<p>A <code>RequirementConstraintMembership</code> is a <code>FeatureMembership</code> for an assumed or required <code>ConstraintUsage</code> of a <code>RequirementDefinition</code> or <code>RequirementUsage<code>.</p>
referencedConstraint =
    let referencedFeature : Feature = 
        ownedConstraint.referencedFeatureTarget() in
    if referencedFeature = null then ownedConstraint
    else if referencedFeature.oclIsKindOf(ConstraintUsage) then
        refrencedFeature.oclAsType(ConstraintUsage)
    else null
    endif endif
owningType.oclIsKindOf(RequirementDefinition) or
owningType.oclIsKindOf(RequirementUsage)
ownedConstraint.isComposite"""
    kind = EAttribute(eType=RequirementConstraintKind, unique=True, derived=False, changeable=True)
    _ownedConstraint = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='ownedConstraint', transient=True)
    _referencedConstraint = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='referencedConstraint', transient=True)

    @property
    def ownedConstraint(self):
        raise NotImplementedError('Missing implementation for ownedConstraint')

    @ownedConstraint.setter
    def ownedConstraint(self, value):
        raise NotImplementedError('Missing implementation for ownedConstraint')

    @property
    def referencedConstraint(self):
        raise NotImplementedError('Missing implementation for referencedConstraint')

    @referencedConstraint.setter
    def referencedConstraint(self, value):
        raise NotImplementedError('Missing implementation for referencedConstraint')

    def __init__(self, *, kind=None, ownedConstraint=None, referencedConstraint=None, **kwargs):

        super().__init__(**kwargs)

        if kind is not None:
            self.kind = kind

        if ownedConstraint is not None:
            self.ownedConstraint = ownedConstraint

        if referencedConstraint is not None:
            self.referencedConstraint = referencedConstraint


class ResultExpressionMembership(FeatureMembership):
    """<p>A <code>ResultExpressionMembership</code> is a <code>FeatureMembership</code> that indicates that the <code>ownedResultExpression</code> provides the result values for the <code>Function</code> or <code>Expression</code> that owns it. The owning <code>Function</code> or <code>Expression</code> must contain a <code>BindingConnector</code> between the <code>result</code> <code>parameter</code> of the <code>ownedResultExpression</code> and the <code>result</code> <code>parameter</code> of the owning <code>Function</code> or <code>Expression</code>.</p>

owningType.oclIsKindOf(Function) or owningType.oclIsKindOf(Expression)"""
    _ownedResultExpression = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedResultExpression', transient=True)

    @property
    def ownedResultExpression(self):
        raise NotImplementedError('Missing implementation for ownedResultExpression')

    @ownedResultExpression.setter
    def ownedResultExpression(self, value):
        raise NotImplementedError('Missing implementation for ownedResultExpression')

    def __init__(self, *, ownedResultExpression=None, **kwargs):

        super().__init__(**kwargs)

        if ownedResultExpression is not None:
            self.ownedResultExpression = ownedResultExpression


class StateSubactionMembership(FeatureMembership):
    """<p>A <code>StateSubactionMembership</code> is a <code>FeatureMembership</code> for an entry, do or exit <code>ActionUsage<code> of a <code>StateDefinition</code> or <code>StateUsage</code>.</p>
owningType.oclIsKindOf(StateDefinition) or
owningType.oclIsKindOf(StateUsage)"""
    kind = EAttribute(eType=StateSubactionKind, unique=True, derived=False, changeable=True)
    _action = EReference(ordered=False, unique=True, containment=False,
                         derived=True, name='action', transient=True)

    @property
    def action(self):
        raise NotImplementedError('Missing implementation for action')

    @action.setter
    def action(self, value):
        raise NotImplementedError('Missing implementation for action')

    def __init__(self, *, action=None, kind=None, **kwargs):

        super().__init__(**kwargs)

        if kind is not None:
            self.kind = kind

        if action is not None:
            self.action = action


class Structure(Class):
    """<p>A <code>Structure</code> is a <code>Class</code> of objects in the modeled universe that are primarily structural in nature. While such an object is not itself behavioral, it may be involved in and acted on by <code>Behaviors</code>, and it may be the performer of some of them.</p>

specializesFromLibrary('Objects::Object')
ownedSpecialization.general->forAll(not oclIsKindOf(Behavior))"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class TransitionFeatureMembership(FeatureMembership):
    """<p>A <code>TransitionFeatureMembership</code> is a <code>FeatureMembership</code> for a trigger, guard or effect of a <code>TransitionUsage</code>, whose <code>transitionFeature</code> is a <code>AcceptActionUsage</code>, <em><code>Boolean</code></em>-valued <code>Expression</code> or <code>ActionUsage</code>, depending on its <code>kind</code>. </p>
kind = TransitionFeatureKind::trigger implies
    transitionFeature.oclIsKindOf(AcceptActionUsage)
owningType.oclIsKindOf(TransitionUsage)
kind = TransitionFeatureKind::guard implies
    transitionFeature.oclIsKindOf(Expression) and
    let guard : Expression = transitionFeature.oclIsKindOf(Expression) in
    guard.result.specializesFromLibrary('ScalarValues::Boolean') and
    guard.result.multiplicity <> null and
    guard.result.multiplicity.hasBounds(1,1)
kind = TransitionFeatureKind::effect implies
    transitionFeature.oclIsKindOf(ActionUsage)"""
    kind = EAttribute(eType=TransitionFeatureKind, unique=True, derived=False, changeable=True)
    _transitionFeature = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='transitionFeature', transient=True)

    @property
    def transitionFeature(self):
        raise NotImplementedError('Missing implementation for transitionFeature')

    @transitionFeature.setter
    def transitionFeature(self, value):
        raise NotImplementedError('Missing implementation for transitionFeature')

    def __init__(self, *, kind=None, transitionFeature=None, **kwargs):

        super().__init__(**kwargs)

        if kind is not None:
            self.kind = kind

        if transitionFeature is not None:
            self.transitionFeature = transitionFeature


class ViewRenderingMembership(FeatureMembership):
    """<p>A <code>ViewRenderingMembership</code> is a <coed>FeatureMembership</code> that identifies the <code>viewRendering</code> of a <code>ViewDefinition</code> or <code>ViewUsage</code>.</p>
referencedRendering =
    let referencedFeature : Feature = 
        ownedRendering.referencedFeatureTarget() in
    if referencedFeature = null then ownedRendering
    else if referencedFeature.oclIsKindOf(RenderingUsage) then
        refrencedFeature.oclAsType(RenderingUsage)
    else null
    endif endif
owningType.oclIsKindOf(ViewDefinition) or
owningType.oclIsKindOf(ViewUsage)"""
    _ownedRendering = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='ownedRendering', transient=True)
    _referencedRendering = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='referencedRendering', transient=True)

    @property
    def ownedRendering(self):
        raise NotImplementedError('Missing implementation for ownedRendering')

    @ownedRendering.setter
    def ownedRendering(self, value):
        raise NotImplementedError('Missing implementation for ownedRendering')

    @property
    def referencedRendering(self):
        raise NotImplementedError('Missing implementation for referencedRendering')

    @referencedRendering.setter
    def referencedRendering(self, value):
        raise NotImplementedError('Missing implementation for referencedRendering')

    def __init__(self, *, ownedRendering=None, referencedRendering=None, **kwargs):

        super().__init__(**kwargs)

        if ownedRendering is not None:
            self.ownedRendering = ownedRendering

        if referencedRendering is not None:
            self.referencedRendering = referencedRendering


class ActorMembership(ParameterMembership):
    """<p>An <code>ActorMembership</code> is a <code>ParameterMembership</code> that identifies a <code>PartUsage</code> as an <em>actor</em> <code>parameter</code>, which specifies a role played by an external entity in interaction with the <code>owningType</code> of the <code>ActorMembership</code>.</p>
owningType.oclIsKindOf(RequirementUsage) or
owningType.oclIsKindOf(RequirementDefinition) or
owningType.oclIsKindOf(CaseDefinition) or
owningType.oclIsKindOf(CaseUsage)
"""
    _ownedActorParameter = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedActorParameter', transient=True)

    @property
    def ownedActorParameter(self):
        raise NotImplementedError('Missing implementation for ownedActorParameter')

    @ownedActorParameter.setter
    def ownedActorParameter(self, value):
        raise NotImplementedError('Missing implementation for ownedActorParameter')

    def __init__(self, *, ownedActorParameter=None, **kwargs):

        super().__init__(**kwargs)

        if ownedActorParameter is not None:
            self.ownedActorParameter = ownedActorParameter


class AttributeDefinition(Definition, DataType):
    """<p>An <code>AttributeDefinition</code> is a <code>Definition</code> and a <code>DataType</code> of information about a quality or characteristic of a system or part of a system that has no independent identity other than its value. All <code>features</code> of an <code>AttributeDefinition</code> must be referential (non-composite).</p>

<p>As a <code>DataType</code>, an <code>AttributeDefinition</code> must specialize, directly or indirectly, the base <code>DataType</code> <code><em>Base::DataValue</em></code> from the Kernel Semantic Library.</p>
feature->forAll(not isComposite)"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class BindingConnector(Connector):
    """<p>A <code>BindingConnector</code> is a binary <code>Connector</code> that requires its <code>relatedFeatures</code> to identify the same things (have the same values).</p>

relatedFeature->size() = 2
specializesFromLibrary('Links::selfLinks')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class BooleanExpression(Expression):
    """<p>A <code>BooleanExpression</code> is a <em><code>Boolean</code></em>-valued <code>Expression</code> whose type is a <code>Predicate</code>. It represents a logical condition resulting from the evaluation of the <code>Predicate</code>.</p>

specializesFromLibrary('Performances::booleanEvaluations')"""
    _predicate = EReference(ordered=False, unique=True, containment=False,
                            derived=True, name='predicate', transient=True)

    @property
    def predicate(self):
        raise NotImplementedError('Missing implementation for predicate')

    @predicate.setter
    def predicate(self, value):
        raise NotImplementedError('Missing implementation for predicate')

    def __init__(self, *, predicate=None, **kwargs):

        super().__init__(**kwargs)

        if predicate is not None:
            self.predicate = predicate


class EnumerationUsage(AttributeUsage):
    """<p>An <code>EnumerationUsage</code> is an <code>AttributeUsage</code> whose <code>attributeDefinition</code> is an <code>EnumerationDefinition</code>.</p>"""
    _enumerationDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='enumerationDefinition', transient=True)

    @property
    def enumerationDefinition(self):
        raise NotImplementedError('Missing implementation for enumerationDefinition')

    @enumerationDefinition.setter
    def enumerationDefinition(self, value):
        raise NotImplementedError('Missing implementation for enumerationDefinition')

    def __init__(self, *, enumerationDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if enumerationDefinition is not None:
            self.enumerationDefinition = enumerationDefinition


class EventOccurrenceUsage(OccurrenceUsage):
    """<p>An <code>EventOccurrenceUsage</code> is an <code>OccurrenceUsage</code> that represents another <code>OccurrenceUsage</code> occurring as a <code><em>suboccurrence</em></code> of the containing occurrence of the <code>EventOccurrenceUsage</code>. Unless it is the <code>EventOccurrenceUsage</code> itself, the referenced <code>OccurrenceUsage</code> is related to the <code>EventOccurrenceUsage</code> by a <code>ReferenceSubsetting</code> <code>Relationship</code>.</p>

<p>If the <code>EventOccurrenceUsage</code> is owned by an <code>OccurrenceDefinition</code> or <code>OccurrenceUsage</code>, then it also subsets the <em><code>timeEnclosedOccurrences</code></em> property of the <code>Class</code> <em><code>Occurrence</code></em> from the Kernel Semantic Library model <em><code>Occurrences</code></em>.</p>
eventOccurrence =
    if referencedFeatureTarget() = null then self
    else if referencedFeatureTarget().oclIsKindOf(OccurrenceUsage) then
        referencedFeatureTarget().oclAsType(OccurrenceUsage)
    else null
    endif endif
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(OccurrenceUsage)
owningType <> null and
(owningType.oclIsKindOf(OccurrenceDefinition) or
 owningType.oclIsKindOf(OccurrenceUsage)) implies
    specializesFromLibrary('Occurrences::Occurrence::timeEnclosedOccurrences')
isReference"""
    _eventOccurrence = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='eventOccurrence', transient=True)

    @property
    def eventOccurrence(self):
        raise NotImplementedError('Missing implementation for eventOccurrence')

    @eventOccurrence.setter
    def eventOccurrence(self, value):
        raise NotImplementedError('Missing implementation for eventOccurrence')

    def __init__(self, *, eventOccurrence=None, **kwargs):

        super().__init__(**kwargs)

        if eventOccurrence is not None:
            self.eventOccurrence = eventOccurrence


class FeatureReferenceExpression(Expression):
    """<p>A <code>FeatureReferenceExpression</code> is an <code>Expression</code> whose <code>result</code> is bound to a <code>referent</code> <code>Feature</code>.</p>
referent =
    let nonParameterMemberships : Sequence(Membership) = ownedMembership->
        reject(oclIsKindOf(ParameterMembership)) in
    if nonParameterMemberships->isEmpty() or
       not nonParameterMemberships->first().memberElement.oclIsKindOf(Feature)
    then null
    else nonParameterMemberships->first().memberElement.oclAsType(Feature)
    endif
ownedMember->selectByKind(BindingConnector)->exists(b |
    b.relatedFeatures->includes(targetFeature) and
    b.relatedFeatures->includes(result))
let membership : Membership = 
    ownedMembership->reject(m | m.oclIsKindOf(ParameterMembership)) in
membership->notEmpty() and
membership->at(1).memberElement.oclIsKindOf(Feature)
result.owningType() = self and result.specializes(referent)
result.owningType = self"""
    _referent = EReference(ordered=False, unique=True, containment=False,
                           derived=True, name='referent', transient=True)

    @property
    def referent(self):
        raise NotImplementedError('Missing implementation for referent')

    @referent.setter
    def referent(self, value):
        raise NotImplementedError('Missing implementation for referent')

    def __init__(self, *, referent=None, **kwargs):

        super().__init__(**kwargs)

        if referent is not None:
            self.referent = referent


class FramedConcernMembership(RequirementConstraintMembership):
    """<p>A <code>FramedConcernMembership</code> is a <code>RequirementConstraintMembership</code> for a framed <code>ConcernUsage</code> of a <code>RequirementDefinition</code> or <code>RequirementUsage</code>.</p>
kind = RequirementConstraintKind::requirement"""
    _ownedConcern = EReference(ordered=False, unique=True, containment=False,
                               derived=True, name='ownedConcern', transient=True)
    _referencedConcern = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='referencedConcern', transient=True)

    @property
    def ownedConcern(self):
        raise NotImplementedError('Missing implementation for ownedConcern')

    @ownedConcern.setter
    def ownedConcern(self, value):
        raise NotImplementedError('Missing implementation for ownedConcern')

    @property
    def referencedConcern(self):
        raise NotImplementedError('Missing implementation for referencedConcern')

    @referencedConcern.setter
    def referencedConcern(self, value):
        raise NotImplementedError('Missing implementation for referencedConcern')

    def __init__(self, *, ownedConcern=None, referencedConcern=None, **kwargs):

        super().__init__(**kwargs)

        if ownedConcern is not None:
            self.ownedConcern = ownedConcern

        if referencedConcern is not None:
            self.referencedConcern = referencedConcern


class DerivedExpression(EDerivedCollection):
    pass


class Function(Behavior):
    """<p>A <code>Function</code> is a <code>Behavior</code> that has an <code>out</code> <code>parameter</code> that is identified as its <code>result</code>. A <code>Function</code> represents the performance of a calculation that produces the values of its <code>result</code> <code>parameter</code>. This calculation may be decomposed into <code>Expressions</code> that are <code>steps</code> of the <code>Function</code>.</p>

featureMembership->
    selectByKind(ReturnParameterMembership)->
    size() = 1
specializesFromLibrary('Performances::Evaluation')
ownedMembership.selectByKind(ResultExpressionMembership)->
    forAll(mem | ownedFeature.selectByKind(BindingConnector)->
        exists(binding |
            binding.relatedFeature->includes(result) and
            binding.relatedFeature->includes(mem.ownedResultExpression.result)))
result =
    let resultParams : Sequence(Feature) =
        featureMemberships->
            selectByKind(ReturnParameterMembership).
            ownedMemberParameter in
    if resultParams->notEmpty() then resultParams->first()
    else null
    endif
membership->selectByKind(ResultExpressionMembership)->size() <= 1"""
    _isModelLevelEvaluable = EAttribute(
        eType=EBoolean, unique=True, derived=True, changeable=True, name='isModelLevelEvaluable', transient=True)
    expression = EReference(ordered=False, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedExpression)
    _result = EReference(ordered=False, unique=True, containment=False,
                         derived=True, name='result', transient=True)

    @property
    def isModelLevelEvaluable(self):
        raise NotImplementedError('Missing implementation for isModelLevelEvaluable')

    @isModelLevelEvaluable.setter
    def isModelLevelEvaluable(self, value):
        raise NotImplementedError('Missing implementation for isModelLevelEvaluable')

    @property
    def result(self):
        raise NotImplementedError('Missing implementation for result')

    @result.setter
    def result(self, value):
        raise NotImplementedError('Missing implementation for result')

    def __init__(self, *, expression=None, isModelLevelEvaluable=None, result=None, **kwargs):

        super().__init__(**kwargs)

        if isModelLevelEvaluable is not None:
            self.isModelLevelEvaluable = isModelLevelEvaluable

        if expression:
            self.expression.extend(expression)

        if result is not None:
            self.result = result


class DerivedArgument(EDerivedCollection):
    pass


@abstract
class InstantiationExpression(Expression):
    """<p>An <code>InstantiationExpression</code> is an <code>Expression</code> that instantiates its <code>instantiatedType</code>, binding some or all of the <code>features</code> of that <code>Type</code> to the <code>results</code> of its <code>arguments</code>.</p>

<p><code>InstantiationExpression</code> is abstract, with concrete subclasses <code>InvocationExpression</code> and <code>ConstructorExpression</code>.</p>
result.owningType = self
instantiatedType = instantiatedType()
instantiatedType() <> null"""
    argument = EReference(ordered=True, unique=True, containment=False,
                          derived=True, upper=-1, transient=True, derived_class=DerivedArgument)
    _instantiatedType = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='instantiatedType', transient=True)

    @property
    def instantiatedType(self):
        raise NotImplementedError('Missing implementation for instantiatedType')

    @instantiatedType.setter
    def instantiatedType(self, value):
        raise NotImplementedError('Missing implementation for instantiatedType')

    def __init__(self, *, argument=None, instantiatedType=None, **kwargs):

        super().__init__(**kwargs)

        if argument:
            self.argument.extend(argument)

        if instantiatedType is not None:
            self.instantiatedType = instantiatedType

    def instantiatedType(self):
        """<p>Return the <code>Type</code> to act as the <code>instantiatedType</code> for this <code>InstantiationExpression</code>. By default, this is the <code>memberElement</code> of the first <code>ownedMembership</code> that is not a <code>FeatureMembership</code>, which must be a <code>Type</code>.</p>

<p><b>Note.</b> This operation is overridden in the subclass <code>OperatorExpression</code>.</p>
let members : Sequence(Element) = ownedMembership->
    reject(oclIsKindOf(FeatureMembership)).memberElement in
if members->isEmpty() or not members->first().oclIsKindOf(Type) then null
else typeMembers->first().oclAsType(Type)
endif"""
        raise NotImplementedError('operation instantiatedType(...) not yet implemented')


class DerivedItemdefinition(EDerivedCollection):
    pass


class ItemUsage(OccurrenceUsage):
    """<p>An <code>ItemUsage</code> is an <code>OccurrenceUsage</code> whose <code>definition</code> is a <code>Structure</code>. Nominally, if the <code>definition</code> is an <code>ItemDefinition</code>, an <code>ItemUsage</code> is a <code>ItemUsage</code> of that <code>ItemDefinition</code> within a system. However, other kinds of Kernel <code>Structures</code> are also allowed, to permit use of <code>Structures</code> from the Kernel Model Libraries.</p>
itemDefinition = occurrenceDefinition->selectByKind(Structure)
specializesFromLibrary('Items::items')
isComposite and owningType <> null and
(owningType.oclIsKindOf(ItemDefinition) or
 owningType.oclIsKindOf(ItemUsage)) implies
    specializesFromLibrary('Items::Item::subitem')"""
    itemDefinition = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedItemdefinition)

    def __init__(self, *, itemDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if itemDefinition:
            self.itemDefinition.extend(itemDefinition)


class LiteralExpression(Expression):
    """<p>A <code>LiteralExpression</code> is an <code>Expression</code> that provides a basic <code><em>DataValue</em></code> as a result.</p>

isModelLevelEvaluable = true
specializesFromLibrary('Performances::literalEvaluations')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class Metaclass(Structure):
    """<p>A <code>Metaclass</code> is a <code>Structure</code> used to type <code>MetadataFeatures</code>.</p>
specializesFromLibrary('Metaobjects::Metaobject')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class MetadataAccessExpression(Expression):
    """<p>A <code>MetadataAccessExpression</code> is an <code>Expression</code> whose <code>result</code> is a sequence of instances of <code>Metaclasses</code> representing all the <code>MetadataFeature</code> annotations of the <code>referencedElement</code>. In addition, the sequence includes an instance of the reflective <code>Metaclass</code> corresponding to the MOF class of the <code>referencedElement</code>, with values for all the abstract syntax properties of the <code>referencedElement</code>.</p>
specializesFromLibrary('Performances::metadataAccessEvaluations')
ownedMembership->exists(not oclIsKindOf(FeatureMembership))
referencedElement =
    let elements : Sequence(Element) = ownedMembership->
        reject(oclIsKindOf(FeatureMembership)).memberElement in
    if elements->isEmpty() then null
    else elements->first()
    endif"""
    _referencedElement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='referencedElement', transient=True)

    @property
    def referencedElement(self):
        raise NotImplementedError('Missing implementation for referencedElement')

    @referencedElement.setter
    def referencedElement(self, value):
        raise NotImplementedError('Missing implementation for referencedElement')

    def __init__(self, *, referencedElement=None, **kwargs):

        super().__init__(**kwargs)

        if referencedElement is not None:
            self.referencedElement = referencedElement

    def metaclassFeature(self):
        """<p>Return a <code>MetadataFeature</code> whose <code>annotatedElement</code> is the <code>referencedElement</code>, whose <code>metaclass</code> is the reflective <code>Metaclass</code> corresponding to the MOF class of the <code>referencedElement</code> and whose <code>ownedFeatures</code> are bound to the MOF properties of the <code>referencedElement</code>.</p>"""
        raise NotImplementedError('operation metaclassFeature(...) not yet implemented')


class NullExpression(Expression):
    """<p>A <code>NullExpression</code> is an <code>Expression</code> that results in a null value.</p>

specializesFromLibrary('Performances::nullEvaluations')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class OccurrenceDefinition(Definition, Class):
    """<p>An <code>OccurrenceDefinition</code> is a <code>Definition</code> of a <code>Class</code> of individuals that have an independent life over time and potentially an extent over space. This includes both structural things and behaviors that act on such structures. If <code>isIndividual</code> is true, then the <code>OccurrenceDefinition</code> is constrained to have (at most) a single instance that is the entire life of a single individual.</p>
isIndividual implies specializesFromLibrary('Occurrences::Life')
isIndividual implies
    multiplicity <> null and
    multiplicity.specializesFromLibrary('Base::zeroOrOne')"""
    isIndividual = EAttribute(eType=EBoolean, unique=True, derived=False,
                              changeable=True, default_value=False)

    def __init__(self, *, isIndividual=None, **kwargs):

        super().__init__(**kwargs)

        if isIndividual is not None:
            self.isIndividual = isIndividual


class DerivedPortdefinition(EDerivedCollection):
    pass


class PortUsage(OccurrenceUsage):
    """<p>A <code>PortUsage</code> is a usage of a <code>PortDefinition</code>. A <code>PortUsage</code> itself as well as all its <code>nestedUsages</code> must be referential (non-composite).</p>
nestedUsage->
    reject(oclIsKindOf(PortUsage))->
    forAll(not isComposite)
specializesFromLibrary('Ports::ports')
isComposite and owningType <> null and
(owningType.oclIsKindOf(PortDefinition) or
 owningType.oclIsKindOf(PortUsage)) implies
    specializesFromLibrary('Ports::Port::subports')
owningType = null or
not owningType.oclIsKindOf(PortDefinition) and
not owningType.oclIsKindOf(PortUsage) implies
    isReference
owningType <> null and
(owningType.oclIsKindOf(PartDefinition) or
 owningType.oclIsKindOf(PartUsage)) implies
    specializesFromLibrary('Parts::Part::ownedPorts')"""
    portDefinition = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedPortdefinition)

    def __init__(self, *, portDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if portDefinition:
            self.portDefinition.extend(portDefinition)


class RequirementVerificationMembership(RequirementConstraintMembership):
    """<p>A <code>RequirementVerificationMembership</code> is a <code>RequirementConstraintMembership </code> used in the objective of a <code>VerificationCase</code> to identify a <code>RequirementUsage</code> that is verified by the <code>VerificationCase</code>.</p>
kind = RequirementConstraintKind::requirement
owningType.oclIsKindOf(RequirementUsage) and
owningType.owningFeatureMembership <> null and
owningType.owningFeatureMembership.oclIsKindOf(ObjectiveMembership)"""
    _ownedRequirement = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='ownedRequirement', transient=True)
    _verifiedRequirement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='verifiedRequirement', transient=True)

    @property
    def ownedRequirement(self):
        raise NotImplementedError('Missing implementation for ownedRequirement')

    @ownedRequirement.setter
    def ownedRequirement(self, value):
        raise NotImplementedError('Missing implementation for ownedRequirement')

    @property
    def verifiedRequirement(self):
        raise NotImplementedError('Missing implementation for verifiedRequirement')

    @verifiedRequirement.setter
    def verifiedRequirement(self, value):
        raise NotImplementedError('Missing implementation for verifiedRequirement')

    def __init__(self, *, ownedRequirement=None, verifiedRequirement=None, **kwargs):

        super().__init__(**kwargs)

        if ownedRequirement is not None:
            self.ownedRequirement = ownedRequirement

        if verifiedRequirement is not None:
            self.verifiedRequirement = verifiedRequirement


class ReturnParameterMembership(ParameterMembership):
    """<p>A <code>ReturnParameterMembership</code> is a <code>ParameterMembership</code> that indicates that the <code>ownedMemberParameter</code> is the <code>result</code> <code>parameter</code> of a <code>Function</code> or <code>Expression</code>. The <code>direction</code> of the <code>ownedMemberParameter</code> must be <code>out</code>.</p>

owningType.oclIsKindOf(Function) or owningType.oclIsKindOf(Expression)"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class StakeholderMembership(ParameterMembership):
    """<p>A <code>StakeholderMembership</code> is a <code>ParameterMembership</code> that identifies a <code>PartUsage</code> as a <code>stakeholderParameter</code> of a <code>RequirementDefinition</code> or <code>RequirementUsage</code>, which specifies a role played by an entity with concerns framed by the <code>owningType</code>.</p>
owningType.oclIsKindOf(RequirementUsage) or
owningType.oclIsKindOf(RequirementDefinition)"""
    _ownedStakeholderParameter = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedStakeholderParameter', transient=True)

    @property
    def ownedStakeholderParameter(self):
        raise NotImplementedError('Missing implementation for ownedStakeholderParameter')

    @ownedStakeholderParameter.setter
    def ownedStakeholderParameter(self, value):
        raise NotImplementedError('Missing implementation for ownedStakeholderParameter')

    def __init__(self, *, ownedStakeholderParameter=None, **kwargs):

        super().__init__(**kwargs)

        if ownedStakeholderParameter is not None:
            self.ownedStakeholderParameter = ownedStakeholderParameter


class SubjectMembership(ParameterMembership):
    """<p>A <code>SubjectMembership</code> is a <code>ParameterMembership</code> that indicates that its <code>ownedSubjectParameter</code> is the subject of its <code>owningType</code>. The <code>owningType</code> of a <code>SubjectMembership</code> must be a <code>RequirementDefinition</code>, <code>RequirementUsage</code>, <code>CaseDefinition</code>, or <code>CaseUsage</code>.</p>
owningType.oclIsType(RequirementDefinition) or
owningType.oclIsType(RequiremenCaseRequirementDefinition) or
owningType.oclIsType(CaseDefinition) or
owningType.oclIsType(CaseUsage)
"""
    _ownedSubjectParameter = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedSubjectParameter', transient=True)

    @property
    def ownedSubjectParameter(self):
        raise NotImplementedError('Missing implementation for ownedSubjectParameter')

    @ownedSubjectParameter.setter
    def ownedSubjectParameter(self, value):
        raise NotImplementedError('Missing implementation for ownedSubjectParameter')

    def __init__(self, *, ownedSubjectParameter=None, **kwargs):

        super().__init__(**kwargs)

        if ownedSubjectParameter is not None:
            self.ownedSubjectParameter = ownedSubjectParameter


class Succession(Connector):
    """<p>A <code>Succession</code> is a binary <code>Connector</code> that requires its <code>relatedFeatures</code> to happen separately in time.</p>

specializesFromLibrary('Occurrences::happensBeforeLinks')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedActiondefinition(EDerivedCollection):
    pass


class ActionUsage(OccurrenceUsage, Step):
    """<p>An <code>ActionUsage</code> is a <code>Usage</code> that is also a <code>Step</code>, and, so, is typed by a <code>Behavior</code>. Nominally, if the type is an <code>ActionDefinition</code>, an <code>ActionUsage</code> is a <code>Usage</code> of that <code>ActionDefinition</code> within a system. However, other kinds of kernel <code>Behaviors</code> are also allowed, to permit use of <code>Behaviors</code> from the Kernel Model Libraries.</p>

isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::subactions')
specializesFromLibrary('Actions::actions')
isComposite and owningType <> null and
(owningType.oclIsKindOf(PartDefinition) or
 owningType.oclIsKindOf(PartUsage)) implies
    specializesFromLibrary('Parts::Part::ownedActions')
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(StateSubactionMembership) implies
    let kind : StateSubactionKind = 
        owningFeatureMembership.oclAsType(StateSubactionMembership).kind in
    if kind = StateSubactionKind::entry then
        redefinesFromLibrary('States::StateAction::entryAction')
    else if kind = StateSubactionKind::do then
        redefinesFromLibrary('States::StateAction::doAction')
    else
        redefinesFromLibrary('States::StateAction::exitAction')
    endif endif"""
    actionDefinition = EReference(ordered=True, unique=True, containment=False,
                                  derived=True, upper=-1, transient=True, derived_class=DerivedActiondefinition)

    def __init__(self, *, actionDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if actionDefinition:
            self.actionDefinition.extend(actionDefinition)

    def argument(self, i=None):
        """<p>Return the <code>i</code>-th argument <code>Expression</code> of an <code>ActionUsage</code>, defined as the <code>value</code> <code>Expression</code> of the <code>FeatureValue</code> of the <code>i</code>-th owned input <code>parameter</code> of the <code>ActionUsage</code>. Return null if the <code>ActionUsage</code> has less than <code>i</code> owned input <code>parameters</code> or the <code>i</code>-th owned input <code>parameter</code> has no <code>FeatureValue</code>.</p>
if inputParameter(i) = null then null
else
    let featureValue : Sequence(FeatureValue) = inputParameter(i).
        ownedMembership->select(oclIsKindOf(FeatureValue)) in
    if featureValue->isEmpty() then null
    else featureValue->at(1).value
    endif
endif"""
        raise NotImplementedError('operation argument(...) not yet implemented')

    def inputParameter(self, i=None):
        """<p>Return the <code>i</code>-th owned input <code>parameter</code> of the <code>ActionUsage</code>. Return null if the <code>ActionUsage</code> has less than <code>i</code> owned input <code>parameters</code>.</p>
if inputParameters()->size() < i then null
else inputParameters()->at(i)
endif"""
        raise NotImplementedError('operation inputParameter(...) not yet implemented')

    def inputParameters(self):
        """<p>Return the owned input <code>parameters</code> of this <code>ActionUsage</code>.</p>
input->select(f | f.owner = self)"""
        raise NotImplementedError('operation inputParameters(...) not yet implemented')

    def isSubactionUsage(self):
        """<p>Check if this <code>ActionUsage</code> is composite and has an <code>owningType</code> that is an <code>ActionDefinition</code> or <code>ActionUsage</code> but is <em>not</em> the <code>entryAction</code> or <code>exitAction</em></code> of a <code>StateDefinition</code> or <code>StateUsage</code>. If so, then it represents an <code><em>Action</em></code> that is a <code><em>subaction</em></code> of another <code><em>Action</em></code>.</p>
isComposite and owningType <> null and
(owningType.oclIsKindOf(ActionDefinition) or
 owningType.oclIsKindOf(ActionUsage)) and
(owningFeatureMembership.oclIsKindOf(StateSubactionMembership) implies
 owningFeatureMembership.oclAsType(StateSubactionMembership).kind = 
    StateSubactionKind::do)"""
        raise NotImplementedError('operation isSubactionUsage(...) not yet implemented')


@abstract
class ConnectorAsUsage(Usage, Connector):
    """<p>A <code>ConnectorAsUsage</code> is both a <code>Connector</code> and a <code>Usage</code>. <code>ConnectorAsUsage</code> cannot itself be instantiated in a SysML model, but it is a base class for the concrete classes <code>BindingConnectorAsUsage</code>, <code>SuccessionAsUsage</code>, <code>ConnectionUsage</code> and <code>FlowUsage</code>.</p>"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class ConstructorExpression(InstantiationExpression):
    """<p>A <code>ConstructorExpression</code> is an <code>InstantiationExpression</code> whose <code>result</code> specializes its <code>instantiatedType</code>, binding some or all of the <code>features</code> of the <code>instantiatedType</code> to the <code>results</code> of its <code>argument</code> <code>Expressions</code>.</p>
instantiatedType.feature->collect(f | 
    result.ownedFeatures->select(redefines(f)).valuation->
    select(v | v <> null).value
)
let features : OrderedSet(Feature) = instantiatedType.feature->
    select(visibility = VisibilityKind::public) in
result.ownedFeature->forAll(f1 | result.ownedFeature->forAll(f2 |
    f1 <> f2 implies
        f1.ownedRedefinition.redefinedFeature->
            intersection(f2.ownedRedefinition.redefinedFeature)->
            intersection(features)->isEmpty()))
let features : OrderedSet(Feature) = instantiatedType.feature->
    select(owningMembership.visibility = VisibilityKind::public) in
result.ownedFeature->forAll(f | 
    f.ownedRedefinition.redefinedFeature->
        intersection(features)->size() = 1)
TBD
specializes('Performances::constructorEvaluations')
result.specializes(instantiatedType)
ownedFeatures->excluding(result)->isEmpty()"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedEnumeratedvalue(EDerivedCollection):
    pass


class EnumerationDefinition(AttributeDefinition):
    """<p>An <code>EnumerationDefinition</code> is an <code>AttributeDefinition</code> all of whose instances are given by an explicit list of <code>enumeratedValues</code>. This is realized by requiring that the <code>EnumerationDefinition</code> have <code>isVariation = true</code>, with the <code>enumeratedValues</code> being its <code>variants</code>.</p> 
isVariation"""
    enumeratedValue = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedEnumeratedvalue)

    def __init__(self, *, enumeratedValue=None, **kwargs):

        super().__init__(**kwargs)

        if enumeratedValue:
            self.enumeratedValue.extend(enumeratedValue)


class DerivedFlowend(EDerivedCollection):
    pass


class DerivedInteraction(EDerivedCollection):
    pass


class DerivedPayloadtype(EDerivedCollection):
    pass


class Flow(Connector, Step):
    """<p>An <code>Flow</code> is a <code>Step</code> that represents the transfer of values from one <code>Feature</code> to another. <code>Flows</code> can take non-zero time to complete.</p>

specializesFromLibrary('Transfers::transfers')
payloadType =
    if payloadFeature = null then Sequence{}
    else payloadFeature.type
    endif
sourceOutputFeature =
    if connectorEnd->isEmpty() or 
        connectorEnd.ownedFeature->isEmpty()
    then null
    else connectorEnd.ownedFeature->first()
    endif
targetInputFeature =
    if connectorEnd->size() < 2 or 
        connectorEnd->at(2).ownedFeature->isEmpty()
    then null
    else connectorEnd->at(2).ownedFeature->first()
    endif
flowEnd = connectorEnd->selectByKind(FlowEnd)
payloadFeature =
    let payloadFeatures : Sequence(PayloadFeature) =
        ownedFeature->selectByKind(PayloadFeature) in
    if payloadFeatures->isEmpty() then null
    else payloadFeatures->first()
    endif
ownedFeature->selectByKind(PayloadFeature)->size() <= 1
ownedEndFeatures->notEmpty() implies
    specializesFromLibrary('Transfers::flowTransfers')"""
    flowEnd = EReference(ordered=True, unique=True, containment=False,
                         derived=True, upper=-1, transient=True, derived_class=DerivedFlowend)
    interaction = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedInteraction)
    _payloadFeature = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='payloadFeature', transient=True)
    payloadType = EReference(ordered=True, unique=False, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedPayloadtype)
    _sourceOutputFeature = EReference(
        ordered=True, unique=False, containment=False, derived=True, name='sourceOutputFeature', transient=True)
    _targetInputFeature = EReference(
        ordered=True, unique=False, containment=False, derived=True, name='targetInputFeature', transient=True)

    @property
    def payloadFeature(self):
        raise NotImplementedError('Missing implementation for payloadFeature')

    @payloadFeature.setter
    def payloadFeature(self, value):
        raise NotImplementedError('Missing implementation for payloadFeature')

    @property
    def sourceOutputFeature(self):
        raise NotImplementedError('Missing implementation for sourceOutputFeature')

    @sourceOutputFeature.setter
    def sourceOutputFeature(self, value):
        raise NotImplementedError('Missing implementation for sourceOutputFeature')

    @property
    def targetInputFeature(self):
        raise NotImplementedError('Missing implementation for targetInputFeature')

    @targetInputFeature.setter
    def targetInputFeature(self, value):
        raise NotImplementedError('Missing implementation for targetInputFeature')

    def __init__(self, *, flowEnd=None, interaction=None, payloadFeature=None, payloadType=None, sourceOutputFeature=None, targetInputFeature=None, **kwargs):

        super().__init__(**kwargs)

        if flowEnd:
            self.flowEnd.extend(flowEnd)

        if interaction:
            self.interaction.extend(interaction)

        if payloadFeature is not None:
            self.payloadFeature = payloadFeature

        if payloadType:
            self.payloadType.extend(payloadType)

        if sourceOutputFeature is not None:
            self.sourceOutputFeature = sourceOutputFeature

        if targetInputFeature is not None:
            self.targetInputFeature = targetInputFeature


class Invariant(BooleanExpression):
    """<p>An <code>Invariant</code> is a <code>BooleanExpression</code> that is asserted to have a specific <code><em>Boolean</em></code> result value. If <code>isNegated = false</code>, then the result is asserted to be true. If <code>isNegated = true</code>, then the result is asserted to be false.</p>

if isNegated then
    specializesFromLibrary('Performances::falseEvaluations')
else
    specializesFromLibrary('Performances::trueEvaluations')
endif"""
    isNegated = EAttribute(eType=EBoolean, unique=True, derived=False,
                           changeable=True, default_value=False)

    def __init__(self, *, isNegated=None, **kwargs):

        super().__init__(**kwargs)

        if isNegated is not None:
            self.isNegated = isNegated


class DerivedOperand(EDerivedCollection):
    pass


class InvocationExpression(InstantiationExpression):
    """<p>An <code>InvocationExpression</code> is an <code>InstantiationExpression</code> whose <code>instantiatedType</code> must be a <code>Behavior</code> or a <code>Feature</code> typed by a single <code>Behavior</code> (such as a <code>Step</code>). Each of the input <code>parameters</code> of the <code>instantiatedType</code> are bound to the <code>result</code> of an <code>argument</code> <code>Expression</code>. If the <code>instantiatedType</code> is a <code>Function</code> or a <code>Feature</code> typed by a <code>Function</code>, then the <code>result</code> of the <code>InvocationExpression</code> is the <code>result</code> of the invoked <code>Function</code>. Otherwise, the <code>result</code> is an instance of the <code>instantiatedType</code> (essentially like a behavioral <code>ConstructorExpression</code>).</p>

not instantiatedType.oclIsKindOf(Function) and
not (instantiatedType.oclIsKindOf(Feature) and 
     instantiatedType.oclAsType(Feature).type->exists(oclIsKindOf(Function))) implies
    ownedFeature.selectByKind(BindingConnector)->exists(
        relatedFeature->includes(self) and
        relatedFeature->includes(result))
TBD
instantiatedType.input->collect(inp | 
    ownedFeatures->select(redefines(inp)).valuation->
    select(v | v <> null).value
)
let parameters : OrderedSet(Feature) = instantiatedType.input in
input->forAll(inp | 
    inp.ownedRedefinition.redefinedFeature->
        intersection(parameters)->size() = 1)
let features : OrderedSet(Feature) = instantiatedType.feature in
input->forAll(inp1 | input->forAll(inp2 |
    inp1 <> inp2 implies
        inp1.ownedRedefinition.redefinedFeature->
            intersection(inp2.ownedRedefinition.redefinedFeature)->
            intersection(features)->isEmpty()))
not instantiatedType.oclIsKindOf(Function) and
not (instantiatedType.oclIsKindOf(Feature) and 
     instantiatedType.oclAsType(Feature).type->exists(oclIsKindOf(Function))) implies
    result.specializes(instantiatedType)
specializes(instantiatedType)
instantiatedType.oclIsKindOf(Behavior) or
instantiatedType.oclIsKindOf(Feature) and
    instantiatedType.type->exists(oclIsKindOf(Behavior)) and
    instantiatedType.type->size(1)
ownedFeature->forAll(f |
    f <> result implies 
        f.direction = FeatureDirectionKind::_'in')"""
    operand = EReference(ordered=True, unique=True, containment=True, derived=True,
                         upper=-1, transient=True, derived_class=DerivedOperand)

    def __init__(self, *, operand=None, **kwargs):

        super().__init__(**kwargs)

        if operand:
            self.operand.extend(operand)


class LiteralBoolean(LiteralExpression):
    """<p><code>LiteralBoolean</code> is a <code>LiteralExpression</code> that provides a <code><em>Boolean</em></code> value as a result. Its <code>result</code> <code>parameter</code> must have type <code><em>Boolean</em></code>.</p>

specializesFromLibrary('Performances::literalBooleanEvaluations')"""
    value = EAttribute(eType=EBoolean, unique=True, derived=False, changeable=True)

    def __init__(self, *, value=None, **kwargs):

        super().__init__(**kwargs)

        if value is not None:
            self.value = value


class LiteralInfinity(LiteralExpression):
    """<p>A <code>LiteralInfinity</code> is a <code>LiteralExpression</code> that provides the positive infinity value (<code>*</code>). It's <code>result</code> must have the type <code><em>Positive</em></code>.</p>

specializesFromLibrary('Performances::literalIntegerEvaluations')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class LiteralInteger(LiteralExpression):
    """<p>A <code>LiteralInteger</code> is a <code>LiteralExpression</code> that provides an <code><em>Integer</em></code> value as a result. Its <code>result</code> <code>parameter</code> must have the type <code><em>Integer</em></code>.</p>

specializesFromLibrary('Performances::literalIntegerEvaluations')"""
    value = EAttribute(eType=EInt, unique=True, derived=False, changeable=True)

    def __init__(self, *, value=None, **kwargs):

        super().__init__(**kwargs)

        if value is not None:
            self.value = value


class LiteralRational(LiteralExpression):
    """<p>A <code>LiteralRational</code> is a <code>LiteralExpression</code> that provides a <code><em>Rational</em></code> value as a result. Its <code>result</code> <code>parameter</code> must have the type <code><em>Rational</em></code>.</p>

specializesFromLibrary('Performances::literalRationalEvaluations')"""
    value = EAttribute(eType=EDouble, unique=True, derived=False, changeable=True)

    def __init__(self, *, value=None, **kwargs):

        super().__init__(**kwargs)

        if value is not None:
            self.value = value


class LiteralString(LiteralExpression):
    """<p>A <code>LiteralString</code> is a <code>LiteralExpression</code> that provides a <code><em>String</em></code> value as a result. Its <code>result</code> <code>parameter</code> must have the type <code><em>String</em></code>.</p>

specializesFromLibrary('Performances::literalStringEvaluations')"""
    value = EAttribute(eType=EString, unique=True, derived=False, changeable=True)

    def __init__(self, *, value=None, **kwargs):

        super().__init__(**kwargs)

        if value is not None:
            self.value = value


class DerivedPartdefinition(EDerivedCollection):
    pass


class PartUsage(ItemUsage):
    """<p>A <code>PartUsage</code> is a usage of a <code>PartDefinition</code> to represent a system or a part of a system. At least one of the <code>itemDefinitions</code> of the <code>PartUsage</code> must be a <code>PartDefinition</code>.</p>

<p>A <code>PartUsage</code> must subset, directly or indirectly, the base <code>PartUsage</code> <em><code>parts</code></em> from the Systems Model Library.</p>
itemDefinition->selectByKind(PartDefinition)
partDefinition->notEmpty()
specializesFromLibrary('Parts::parts')
isComposite and owningType <> null and
(owningType.oclIsKindOf(ItemDefinition) or
 owningType.oclIsKindOf(ItemUsage)) implies
    specializesFromLibrary('Items::Item::subparts')
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(ActorMembership) implies
    if owningType.oclIsKindOf(RequirementDefinition) or 
       owningType.oclIsKindOf(RequirementUsage)
    then specializesFromLibrary('Requirements::RequirementCheck::actors')
    else specializesFromLibrary('Cases::Case::actors')
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(StakeholderMembership) implies
    specializesFromLibrary('Requirements::RequirementCheck::stakeholders')"""
    partDefinition = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedPartdefinition)

    def __init__(self, *, partDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if partDefinition:
            self.partDefinition.extend(partDefinition)


class Predicate(Function):
    """<p>A <code>Predicate</code> is a <code>Function</code> whose <code>result</code> <code>parameter</code> has type <code><em>Boolean</em></code> and multiplicity <code>1..1</code>.</p>

specializesFromLibrary('Performances::BooleanEvaluation')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class AcceptActionUsage(ActionUsage):
    """<p>An <code>AcceptActionUsage</code> is an <code>ActionUsage</code> that specifies the acceptance of an <em><code>incomingTransfer</code></em> from the <code><em>Occurrence</em></code> given by the result of its <code>receiverArgument</code> Expression. (If no <code>receiverArgument</code> is provided, the default is the <em><code>this</code></em> context of the AcceptActionUsage.) The payload of the accepted <em><code>Transfer</em></code> is output on its <code>payloadParameter</code>. Which <em><code>Transfers</em></code> may be accepted is determined by conformance to the typing and (potentially) binding of the <code>payloadParameter</code>.</p>

inputParameters()->notEmpty()
receiverArgument = argument(2)
payloadArgument = argument(1)
payloadParameter = 
 if parameter->isEmpty() then null
 else parameter->first() endif
not isTriggerAction() implies
    specializesFromLibrary('Actions::acceptActions')
isSubactionUsage() and not isTriggerAction() implies
    specializesFromLibrary('Actions::Action::acceptSubactions')
isTriggerAction() implies
    specializesFromLibrary('Actions::TransitionAction::accepter')
payloadArgument <> null and
payloadArgument.oclIsKindOf(TriggerInvocationExpression) implies
    let invocation : Expression =
        payloadArgument.oclAsType(Expression) in
    parameter->size() >= 2 and
    invocation.parameter->size() >= 2 and        
    ownedFeature->selectByKind(BindingConnector)->exists(b |
        b.relatedFeatures->includes(parameter->at(2)) and
        b.relatedFeatures->includes(invocation.parameter->at(2)))"""
    _payloadArgument = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='payloadArgument', transient=True)
    _payloadParameter = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='payloadParameter', transient=True)
    _receiverArgument = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='receiverArgument', transient=True)

    @property
    def payloadArgument(self):
        raise NotImplementedError('Missing implementation for payloadArgument')

    @payloadArgument.setter
    def payloadArgument(self, value):
        raise NotImplementedError('Missing implementation for payloadArgument')

    @property
    def payloadParameter(self):
        raise NotImplementedError('Missing implementation for payloadParameter')

    @payloadParameter.setter
    def payloadParameter(self, value):
        raise NotImplementedError('Missing implementation for payloadParameter')

    @property
    def receiverArgument(self):
        raise NotImplementedError('Missing implementation for receiverArgument')

    @receiverArgument.setter
    def receiverArgument(self, value):
        raise NotImplementedError('Missing implementation for receiverArgument')

    def __init__(self, *, payloadArgument=None, payloadParameter=None, receiverArgument=None, **kwargs):

        super().__init__(**kwargs)

        if payloadArgument is not None:
            self.payloadArgument = payloadArgument

        if payloadParameter is not None:
            self.payloadParameter = payloadParameter

        if receiverArgument is not None:
            self.receiverArgument = receiverArgument

    def isTriggerAction(self):
        """<p>Check if this <code>AcceptActionUsage</code> is the <code>triggerAction</code> of a <code>TransitionUsage</code>.</p>
owningType <> null and 
owningType.oclIsKindOf(TransitionUsage) and
owningType.oclAsType(TransitionUsage).triggerAction->includes(self)"""
        raise NotImplementedError('operation isTriggerAction(...) not yet implemented')


class DerivedAction(EDerivedCollection):
    pass


class ActionDefinition(OccurrenceDefinition, Behavior):
    """<p>An <code>ActionDefinition</code> is a <code>Definition</code> that is also a <code>Behavior</code> that defines an <em><code>Action</code></em> performed by a system or part of a system.</p>
specializesFromLibrary('Actions::Action')
action = usage->selectByKind(ActionUsage)"""
    action = EReference(ordered=True, unique=True, containment=False, derived=True,
                        upper=-1, transient=True, derived_class=DerivedAction)

    def __init__(self, *, action=None, **kwargs):

        super().__init__(**kwargs)

        if action:
            self.action.extend(action)


class AssignmentActionUsage(ActionUsage):
    """<p>An <code>AssignmentActionUsage</code> is an <code>ActionUsage</code> that is defined, directly or indirectly, by the <code>ActionDefinition</code> <em><code>AssignmentAction</code></em> from the Systems Model Library. It specifies that the value of the <code>referent</code> <code>Feature</code>, relative to the target given by the result of the <code>targetArgument</code> <code>Expression</code>, should be set to the result of the <code>valueExpression</code>.</p>

specializesFromLibrary('Actions::assignmentActions')
let targetParameter : Feature = inputParameter(1) in
targetParameter <> null and
targetParameter.ownedFeature->notEmpty() and
targetParameter.ownedFeature->first().
    redefinesFromLibrary('AssignmentAction::target::startingAt')
valueExpression = argument(2)
targetArgument = argument(1)
isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::assignments')
let targetParameter : Feature = inputParameter(1) in
targetParameter <> null and
targetParameter.ownedFeature->notEmpty() and
targetParameter.ownedFeature->first().ownedFeature->notEmpty() and
targetParameter.ownedFeature->first().ownedFeature->first().
    redefinesFromLibrary('AssigmentAction::target::startingAt::accessedFeature')
let targetParameter : Feature = inputParameter(1) in
targetParameter <> null and
targetParameter.ownedFeature->notEmpty() and
targetParameter.ownedFeature->first().ownedFeature->notEmpty() and
targetParameter.ownedFeature->first().ownedFeature->first().redefines(referent)
referent =
    let unownedFeatures : Sequence(Feature) = ownedMembership->
        reject(oclIsKindOf(FeatureMembership)).memberElement->
        select(oclIsKindOf(Feature) and 
               not oclIsKindOf(MetadataFeature)) in
    if unownedFeatures->isEmpty() then null
    else unownedFeatures->first().oclAsType(Feature)
    endif
ownedMembership->exists(
    not oclIsKindOf(OwningMembership) and 
    memberElement.oclIsKindOf(Feature) and
    not memberElement.oclIsKindOf(MetadataFeature))
referent <> null implies referent.featureTarget.isVariable"""
    _referent = EReference(ordered=False, unique=True, containment=False,
                           derived=True, name='referent', transient=True)
    _targetArgument = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='targetArgument', transient=True)
    _valueExpression = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='valueExpression', transient=True)

    @property
    def referent(self):
        raise NotImplementedError('Missing implementation for referent')

    @referent.setter
    def referent(self, value):
        raise NotImplementedError('Missing implementation for referent')

    @property
    def targetArgument(self):
        raise NotImplementedError('Missing implementation for targetArgument')

    @targetArgument.setter
    def targetArgument(self, value):
        raise NotImplementedError('Missing implementation for targetArgument')

    @property
    def valueExpression(self):
        raise NotImplementedError('Missing implementation for valueExpression')

    @valueExpression.setter
    def valueExpression(self, value):
        raise NotImplementedError('Missing implementation for valueExpression')

    def __init__(self, *, referent=None, targetArgument=None, valueExpression=None, **kwargs):

        super().__init__(**kwargs)

        if referent is not None:
            self.referent = referent

        if targetArgument is not None:
            self.targetArgument = targetArgument

        if valueExpression is not None:
            self.valueExpression = valueExpression


class AssociationStructure(Association, Structure):
    """<p>An <code>AssociationStructure</code> is an <code>Association</code> that is also a <code>Structure</code>, classifying link objects that are both links and objects. As objects, link objects can be created and destroyed, and their non-end <code>Features</code> can change over time. However, the values of the end <code>Features</code> of a link object are fixed and cannot change over its lifetime.</p>
specializesFromLibrary('Objects::LinkObject')
endFeature->size() = 2 implies
    specializesFromLibrary('Objects::BinaryLinkObject')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


@abstract
class ControlNode(ActionUsage):
    """<p>A <code>ControlNode</code> is an <code>ActionUsage</code> that does not have any inherent behavior but provides constraints on incoming and outgoing <code>Successions</code> that are used to control other <code>Actions</code>. A <code>ControlNode</code> must be a composite owned <code>usage</code> of an <code>ActionDefinition</code> or <code>ActionUsage</code>.</p>

sourceConnector->selectByKind(Succession)->
    collect(connectorEnd->at(1).multiplicity)->
    forAll(sourceMult | 
        multiplicityHasBounds(sourceMult, 1, 1))
owningType <> null and 
(owningType.oclIsKindOf(ActionDefinition) or
 owningType.oclIsKindOf(ActionUsage))
targetConnector->selectByKind(Succession)->
    collect(connectorEnd->at(2).multiplicity)->
    forAll(targetMult | 
        multiplicityHasBounds(targetMult, 1, 1))
specializesFromLibrary('Action::Action::controls')
isComposite"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

    def multiplicityHasBounds(self, mult=None, lower=None, upper=None):
        """<p>Check that the given <code>Multiplicity</code> has <code>lowerBound</code> and <code>upperBound</code> expressions that are model-level evaluable to the given <code>lower</code> and <code>upper</code> values.</p>
mult <> null and
if mult.oclIsKindOf(MultiplicityRange) then
    mult.oclAsType(MultiplicityRange).hasBounds(lower, upper)
else
    mult.allSuperTypes()->exists(
        oclisKindOf(MultiplicityRange) and
        oclAsType(MultiplicityRange).hasBounds(lower, upper)
endif"""
        raise NotImplementedError('operation multiplicityHasBounds(...) not yet implemented')


class IfActionUsage(ActionUsage):
    """<p>An <code>IfActionUsage</code> is an <code>ActionUsage</code> that specifies that the <code>thenAction</code> <code>ActionUsage</code> should be performed if the result of the <code>ifArgument</code> <code>Expression</code> is true. It may also optionally specify an <code>elseAction</code> <code>ActionUsage</code> that is performed if the result of the <code>ifArgument</code> is false.</p>
thenAction = 
    let parameter : Feature = inputParameter(2) in
    if parameter <> null and parameter.oclIsKindOf(ActionUsage) then
        parameter.oclAsType(ActionUsage)
    else
        null
    endif
isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::ifSubactions')
if elseAction = null then
    specializesFromLibrary('Actions::ifThenActions')
else
    specializesFromLibrary('Actions::ifThenElseActions')
endif
ifArgument = 
    let parameter : Feature = inputParameter(1) in
    if parameter <> null and parameter.oclIsKindOf(Expression) then
        parameter.oclAsType(Expression)
    else
        null
    endif
elseAction = 
    let parameter : Feature = inputParameter(3) in
    if parameter <> null and parameter.oclIsKindOf(ActionUsage) then
        parameter.oclAsType(ActionUsage)
    else
        null
    endif
inputParameters()->size() >= 2"""
    _elseAction = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='elseAction', transient=True)
    _ifArgument = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='ifArgument', transient=True)
    _thenAction = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='thenAction', transient=True)

    @property
    def elseAction(self):
        raise NotImplementedError('Missing implementation for elseAction')

    @elseAction.setter
    def elseAction(self, value):
        raise NotImplementedError('Missing implementation for elseAction')

    @property
    def ifArgument(self):
        raise NotImplementedError('Missing implementation for ifArgument')

    @ifArgument.setter
    def ifArgument(self, value):
        raise NotImplementedError('Missing implementation for ifArgument')

    @property
    def thenAction(self):
        raise NotImplementedError('Missing implementation for thenAction')

    @thenAction.setter
    def thenAction(self, value):
        raise NotImplementedError('Missing implementation for thenAction')

    def __init__(self, *, elseAction=None, ifArgument=None, thenAction=None, **kwargs):

        super().__init__(**kwargs)

        if elseAction is not None:
            self.elseAction = elseAction

        if ifArgument is not None:
            self.ifArgument = ifArgument

        if thenAction is not None:
            self.thenAction = thenAction


class Interaction(Association, Behavior):
    """<p>An <code>Interaction</code> is a <code>Behavior</code> that is also an <code>Association</code>, providing a context for multiple objects that have behaviors that impact one another.</p>
"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class ItemDefinition(OccurrenceDefinition, Structure):
    """<p>An <code>ItemDefinition</code> is an <code>OccurrenceDefinition</code> of the <code>Structure</code> of things that may themselves be systems or parts of systems, but may also be things that are acted on by a system or parts of a system, but which do not necessarily perform actions themselves. This includes items that can be exchanged between parts of a system, such as water or electrical signals.</p>

specializesFromLibrary('Items::Item')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


@abstract
class LoopActionUsage(ActionUsage):
    """<p>A <code>LoopActionUsage</code> is an <code>ActionUsage</code> that specifies that its <code>bodyAction</code> should be performed repeatedly. Its subclasses <code>WhileLoopActionUsage</code> and <code>ForLoopActionUsage</code> provide different ways to determine how many times the <code>bodyAction</code> should be performed.</p>
bodyAction =
    let parameter : Feature = inputParameter(2) in
    if parameter <> null and parameter.oclIsKindOf(Action) then
        parameter.oclAsType(Action)
    else
        null
    endif
"""
    _bodyAction = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='bodyAction', transient=True)

    @property
    def bodyAction(self):
        raise NotImplementedError('Missing implementation for bodyAction')

    @bodyAction.setter
    def bodyAction(self, value):
        raise NotImplementedError('Missing implementation for bodyAction')

    def __init__(self, *, bodyAction=None, **kwargs):

        super().__init__(**kwargs)

        if bodyAction is not None:
            self.bodyAction = bodyAction


class OperatorExpression(InvocationExpression):
    """<p>An <code>OperatorExpression</code> is an <code>InvocationExpression</code> whose <code>function</code> is determined by resolving its <code>operator</code> in the context of one of the standard packages from the Kernel Function Library.</p>"""
    operator = EAttribute(eType=EString, unique=True, derived=False, changeable=True)

    def __init__(self, *, operator=None, **kwargs):

        super().__init__(**kwargs)

        if operator is not None:
            self.operator = operator


class PortDefinition(OccurrenceDefinition, Structure):
    """<p>A <code>PortDefinition</code> defines a point at which external entities can connect to and interact with a system or part of a system. Any <code>ownedUsages</code> of a <code>PortDefinition</code>, other than <code>PortUsages</code>, must not be composite.</p>



conjugatedPortDefinition = 
let conjugatedPortDefinitions : OrderedSet(ConjugatedPortDefinition) =
    ownedMember->selectByKind(ConjugatedPortDefinition) in
if conjugatedPortDefinitions->isEmpty() then null
else conjugatedPortDefinitions->first()
endif
ownedUsage->
    reject(oclIsKindOf(PortUsage))->
    forAll(not isComposite)
not oclIsKindOf(ConjugatedPortDefinition) implies
    ownedMember->
        selectByKind(ConjugatedPortDefinition)->
        size() = 1
specializesFromLibrary('Ports::Port')"""
    _conjugatedPortDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='conjugatedPortDefinition', transient=True)

    @property
    def conjugatedPortDefinition(self):
        raise NotImplementedError('Missing implementation for conjugatedPortDefinition')

    @conjugatedPortDefinition.setter
    def conjugatedPortDefinition(self, value):
        raise NotImplementedError('Missing implementation for conjugatedPortDefinition')

    def __init__(self, *, conjugatedPortDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if conjugatedPortDefinition is not None:
            self.conjugatedPortDefinition = conjugatedPortDefinition


class RenderingUsage(PartUsage):
    """<p>A <code>RenderingUsage</code> is the usage of a <code>RenderingDefinition</code> to specify the rendering of a specific model view to produce a physical view artifact.</p>


specializesFromLibrary('Views::renderings')
owningType <> null and
(owningType.oclIsKindOf(RenderingDefinition) or
 owningType.oclIsKindOf(RenderingUsage)) implies
    specializesFromLibrary('Views::Rendering::subrenderings')
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(ViewRenderingMembership) implies
    redefinesFromLibrary('Views::View::viewRendering')"""
    _renderingDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='renderingDefinition', transient=True)

    @property
    def renderingDefinition(self):
        raise NotImplementedError('Missing implementation for renderingDefinition')

    @renderingDefinition.setter
    def renderingDefinition(self, value):
        raise NotImplementedError('Missing implementation for renderingDefinition')

    def __init__(self, *, renderingDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if renderingDefinition is not None:
            self.renderingDefinition = renderingDefinition


class SendActionUsage(ActionUsage):
    """<p>A <code>SendActionUsage</code> is an <code>ActionUsage</code> that specifies the sending of a payload given by the result of its <code>payloadArgument</code> <code>Expression</code> via a <em><code>MessageTransfer</code></em> whose <em><code>source</code></em> is given by the result of the <code>senderArgument</code> <code>Expression</code> and whose <code>target</code> is given by the result of the <code>receiverArgument</code> <code>Expression</code>. If no <code>senderArgument</code> is provided, the default is the <em><code>this</code></em> context for the action. If no <code>receiverArgument</code> is given, then the receiver is to be determined by, e.g., outgoing <em><code>Connections</code></em> from the sender.</p> 

senderArgument = argument(2)
payloadArgument = argument(1)
owningFeatureMembership <> null and
(owningFeatureMembership.oclIsKindOf(StateSubactionMembership) or
 owningFeatureMembership.oclIsKindOf(TransitionFeatureMembership)) implies
    payloadArgument <> null
receiverArgument = argument(3)
isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::acceptSubactions')
specializesFromLibrary('Actions::sendActions')"""
    _payloadArgument = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='payloadArgument', transient=True)
    _receiverArgument = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='receiverArgument', transient=True)
    _senderArgument = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='senderArgument', transient=True)

    @property
    def payloadArgument(self):
        raise NotImplementedError('Missing implementation for payloadArgument')

    @payloadArgument.setter
    def payloadArgument(self, value):
        raise NotImplementedError('Missing implementation for payloadArgument')

    @property
    def receiverArgument(self):
        raise NotImplementedError('Missing implementation for receiverArgument')

    @receiverArgument.setter
    def receiverArgument(self, value):
        raise NotImplementedError('Missing implementation for receiverArgument')

    @property
    def senderArgument(self):
        raise NotImplementedError('Missing implementation for senderArgument')

    @senderArgument.setter
    def senderArgument(self, value):
        raise NotImplementedError('Missing implementation for senderArgument')

    def __init__(self, *, payloadArgument=None, receiverArgument=None, senderArgument=None, **kwargs):

        super().__init__(**kwargs)

        if payloadArgument is not None:
            self.payloadArgument = payloadArgument

        if receiverArgument is not None:
            self.receiverArgument = receiverArgument

        if senderArgument is not None:
            self.senderArgument = senderArgument


class DerivedStatedefinition(EDerivedCollection):
    pass


class StateUsage(ActionUsage):
    """<p>A <code>StateUsage</code> is an <code>ActionUsage</code> that is nominally the <code>Usage</code> of a <code>StateDefinition</code>. However, other kinds of kernel <code>Behaviors</code> are also allowed as <code>types</code>, to permit use of <code>Behaviors</code from the Kernel Model Libraries.</p>

<p>A <code>StateUsage</code> may be related to up to three of its <code>ownedFeatures</code> by <code>StateSubactionMembership</code> <code>Relationships</code>, all of different <code>kinds</code>, corresponding to the entry, do and exit actions of the <code>StateUsage</code>.</p>

doAction =
    let doMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::do) in
    if doMemberships->isEmpty() then null
    else doMemberships->at(1)
    endif
entryAction =
    let entryMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::entry) in
    if entryMemberships->isEmpty() then null
    else entryMemberships->at(1)
    endif
isParallel implies
    nestedAction.incomingTransition->isEmpty() and
    nestedAction.outgoingTransition->isEmpty()
isSubstateUsage(false) implies
    specializesFromLibrary('States::StateAction::exclusiveStates')
exitAction =
    let exitMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::exit) in
    if exitMemberships->isEmpty() then null
    else exitMemberships->at(1)
    endif
specializesFromLibrary('States::stateActions')
ownedMembership->
    selectByKind(StateSubactionMembership)->
    isUnique(kind)
isSubstateUsage(true) implies
    specializesFromLibrary('States::StateAction::substates')
isComposite and owningType <> null and
(owningType.oclIsKindOf(PartDefinition) or
 owningType.oclIsKindOf(PartUsage)) implies
    specializesFromLibrary('Parts::Part::ownedStates')"""
    isParallel = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)
    _doAction = EReference(ordered=False, unique=True, containment=False,
                           derived=True, name='doAction', transient=True)
    _entryAction = EReference(ordered=False, unique=True, containment=False,
                              derived=True, name='entryAction', transient=True)
    _exitAction = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='exitAction', transient=True)
    stateDefinition = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedStatedefinition)

    @property
    def doAction(self):
        raise NotImplementedError('Missing implementation for doAction')

    @doAction.setter
    def doAction(self, value):
        raise NotImplementedError('Missing implementation for doAction')

    @property
    def entryAction(self):
        raise NotImplementedError('Missing implementation for entryAction')

    @entryAction.setter
    def entryAction(self, value):
        raise NotImplementedError('Missing implementation for entryAction')

    @property
    def exitAction(self):
        raise NotImplementedError('Missing implementation for exitAction')

    @exitAction.setter
    def exitAction(self, value):
        raise NotImplementedError('Missing implementation for exitAction')

    def __init__(self, *, doAction=None, entryAction=None, exitAction=None, isParallel=None, stateDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if isParallel is not None:
            self.isParallel = isParallel

        if doAction is not None:
            self.doAction = doAction

        if entryAction is not None:
            self.entryAction = entryAction

        if exitAction is not None:
            self.exitAction = exitAction

        if stateDefinition:
            self.stateDefinition.extend(stateDefinition)

    def isSubstateUsage(self, isParallel=None):
        """<p>Check if this <code>StateUsage</code> is composite and has an <code>owningType</code> that is a <code>StateDefinition</code> or <code>StateUsage</code> with the given value of <code>isParallel</code>, but is <em>not</em> an <code>entryAction</code>, <code>doAction</code>, or <code>exitAction</code>. If so, then it represents a <code><em>StateAction</em></code> that is a <code><em>substate</em></code> or <code><em>exclusiveState</em></code> (for <code>isParallel = false</code>) of another <code><em>StateAction</em></code>.</p>
isComposite and owningType <> null and
(owningType.oclIsKindOf(StateDefinition) and
    owningType.oclAsType(StateDefinition).isParallel = isParallel or
 owningType.oclIsKindOf(StateUsage) and
    owningType.oclAsType(StateUsage).isParallel = isParallel) and
not owningFeatureMembership.oclIsKindOf(StateSubactionMembership)"""
        raise NotImplementedError('operation isSubstateUsage(...) not yet implemented')


class TerminateActionUsage(ActionUsage):
    """<p>A <code>TerminateActionUsage</code> is an <code>ActionUsage</code> that directly or indirectly specializes the <code>ActionDefinition</code> <em><code>TerminateAction</code></em> from the Systems Model Library, which causes a given <em><code>terminatedOccurrence</code></em> to end during its performance. By default, the <code>terminatedOccurrence</code> is the featuring instance (<em><code>that</code></em>) of the performance of the <code>TerminateActionUsage</code>, generally the performance of its immediately containing <code>ActionDefinition</code> or <code>ActionUsage</code>.</p>
specializesFromLibrary('Actions::terminateActions')
terminatedOccurrenceArgument = argument(1)
isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::terminateSubactions')"""
    _terminatedOccurrenceArgument = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='terminatedOccurrenceArgument', transient=True)

    @property
    def terminatedOccurrenceArgument(self):
        raise NotImplementedError('Missing implementation for terminatedOccurrenceArgument')

    @terminatedOccurrenceArgument.setter
    def terminatedOccurrenceArgument(self, value):
        raise NotImplementedError('Missing implementation for terminatedOccurrenceArgument')

    def __init__(self, *, terminatedOccurrenceArgument=None, **kwargs):

        super().__init__(**kwargs)

        if terminatedOccurrenceArgument is not None:
            self.terminatedOccurrenceArgument = terminatedOccurrenceArgument


class DerivedEffectaction(EDerivedCollection):
    pass


class DerivedGuardexpression(EDerivedCollection):
    pass


class DerivedTriggeraction(EDerivedCollection):
    pass


class TransitionUsage(ActionUsage):
    """<p>A <code>TransitionUsage</code> is an <code>ActionUsage</code> representing a triggered transition between <code>ActionUsages</code> or <code>StateUsages</code>. When triggered by a <code>triggerAction</code>, when its <code>guardExpression</code> is true, the <code>TransitionUsage</code> asserts that its <code>source</code> is exited, then its <code>effectAction</code> (if any) is performed, and then its <code>target</code> is entered.</p>

<p>A <code>TransitionUsage</code> can be related to some of its <code>ownedFeatures</code> using <code>TransitionFeatureMembership</code> <code>Relationships</code>, corresponding to the <code>triggerAction</code>, <code>guardExpression</code> and <code>effectAction</code> of the <code>TransitionUsage</code>.</p>
isComposite and owningType <> null and
(owningType.oclIsKindOf(ActionDefinition) or
 owningType.oclIsKindOf(ActionUsage)) and
source <> null and not source.oclIsKindOf(StateUsage) implies
    specializesFromLibrary('Actions::Action::decisionTransitions')
isComposite and owningType <> null and
(owningType.oclIsKindOf(StateDefinition) or
 owningType.oclIsKindOf(StateUsage)) and
source <> null and source.oclIsKindOf(StateUsage) implies
    specializesFromLibrary('States::StateAction::stateTransitions')

specializesFromLibrary('Actions::transitionActions')
source =
    let sourceFeature : Feature = sourceFeature() in
    if sourceFeature = null then null
    else sourceFeature.featureTarget.oclAsType(ActionUsage)
target =
    if succession.targetFeature->isEmpty() then null
    else
        let targetFeature : Feature =
            succession.targetFeature->first().featureTarget in
        if not targetFeature.oclIsKindOf(ActionUsage) then null
        else targetFeature.oclAsType(ActionUsage)
        endif
    endif

triggerAction = ownedFeatureMembership->
    selectByKind(TransitionFeatureMembership)->
    select(kind = TransitionFeatureKind::trigger).transitionFeature->
    selectByKind(AcceptActionUsage)
let successions : Sequence(Successions) = 
    ownedMember->selectByKind(Succession) in
successions->notEmpty() and
successions->at(1).targetFeature.featureTarget->
    forAll(oclIsKindOf(ActionUsage))
guardExpression = ownedFeatureMembership->
    selectByKind(TransitionFeatureMembership)->
    select(kind = TransitionFeatureKind::trigger).transitionFeature->
    selectByKind(Expression)
triggerAction->forAll(specializesFromLibrary('Actions::TransitionAction::accepter') and
guardExpression->forAll(specializesFromLibrary('Actions::TransitionAction::guard') and
effectAction->forAll(specializesFromLibrary('Actions::TransitionAction::effect'))
triggerAction = ownedFeatureMembership->
    selectByKind(TransitionFeatureMembership)->
    select(kind = TransitionFeatureKind::trigger).transitionFeatures->
    selectByKind(AcceptActionUsage)
succession.sourceFeature = source
ownedMember->selectByKind(BindingConnector)->exists(b |
    b.relatedFeatures->includes(source) and
    b.relatedFeatures->includes(inputParameter(1)))
triggerAction->notEmpty() implies
    let payloadParameter : Feature = inputParameter(2) in
    payloadParameter <> null and
    payloadParameter.subsetsChain(triggerAction->at(1), triggerPayloadParameter())
ownedMember->selectByKind(BindingConnector)->exists(b |
    b.relatedFeatures->includes(succession) and
    b.relatedFeatures->includes(resolveGlobal(
        'TransitionPerformances::TransitionPerformance::transitionLink')))
if triggerAction->isEmpty() then
    inputParameters()->size() >= 1
else
    inputParameters()->size() >= 2
endif

succession = ownedMember->selectByKind(Succession)->at(1)
source <> null and not source.oclIsKindOf(StateUsage) implies
    triggerAction->isEmpty()"""
    effectAction = EReference(ordered=False, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedEffectaction)
    guardExpression = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedGuardexpression)
    _source = EReference(ordered=False, unique=True, containment=False,
                         derived=True, name='source', transient=True)
    _succession = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='succession', transient=True)
    _target = EReference(ordered=False, unique=True, containment=False,
                         derived=True, name='target', transient=True)
    triggerAction = EReference(ordered=False, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedTriggeraction)

    @property
    def source(self):
        raise NotImplementedError('Missing implementation for source')

    @source.setter
    def source(self, value):
        raise NotImplementedError('Missing implementation for source')

    @property
    def succession(self):
        raise NotImplementedError('Missing implementation for succession')

    @succession.setter
    def succession(self, value):
        raise NotImplementedError('Missing implementation for succession')

    @property
    def target(self):
        raise NotImplementedError('Missing implementation for target')

    @target.setter
    def target(self, value):
        raise NotImplementedError('Missing implementation for target')

    def __init__(self, *, effectAction=None, guardExpression=None, source=None, succession=None, target=None, triggerAction=None, **kwargs):

        super().__init__(**kwargs)

        if effectAction:
            self.effectAction.extend(effectAction)

        if guardExpression:
            self.guardExpression.extend(guardExpression)

        if source is not None:
            self.source = source

        if succession is not None:
            self.succession = succession

        if target is not None:
            self.target = target

        if triggerAction:
            self.triggerAction.extend(triggerAction)

    def sourceFeature(self):
        """<p>Return the <code>Feature</code> to be used as the <code>source</code> of the <code>succession</code> of this <code>TransitionUsage</code>, which is the first <code>member</code> of the <code>TransitionUsage</code> that is a <code>Feature</code>, that is owned by the <code>TransitionUsage</code> via a <code>Membership</code> that is <em>not</em> a <code>FeatureMembership</code>, and whose <code>featureTarget</code> is an <code>ActionUsage</code>.</p>
let features : Sequence(Feature) = ownedMembership->
    reject(oclIsKindOf(FeatureMembership)).memberElement->
    selectByKind(Feature)->
    select(featureTarget.oclIsKindOf(ActionUsage)) in
if features->isEmpty() then null
else features->first()
endif"""
        raise NotImplementedError('operation sourceFeature(...) not yet implemented')

    def triggerPayloadParameter(self):
        """<p>Return the <code>payloadParameter</code> of the <code>triggerAction</code> of this <code>TransitionUsage</code>, if it has one.</p>
if triggerAction->isEmpty() then null
else triggerAction->first().payloadParameter
endif"""
        raise NotImplementedError('operation triggerPayloadParameter(...) not yet implemented')


class TriggerInvocationExpression(InvocationExpression):
    """<p>A <code>TriggerInvocationExpression</code> is an <code>InvocationExpression</code> that invokes one of the trigger <code>Functions</code> from the Kernel Semantic Library <code><em>Triggers<em></code> package, as indicated by its <code>kind</code>.</p>
kind = TriggerKind::after implies
    argument->notEmpty() and
    argument->at(1).result.specializesFromLibrary('Quantities::ScalarQuantityValue') and
    let mRef : Element = 
        resolveGlobal('Quantities::TensorQuantityValue::mRef').ownedMemberElement in
    argument->at(1).result.feature->
        select(ownedRedefinition.redefinedFeature->
           closure(ownedRedefinition.redefinedFeature)->
           includes(mRef))->
        exists(specializesFromLibrary('ISQBase::DurationUnit'))
kind = TriggerKind::at implies
    argument->notEmpty() and
    argument->at(1).result.specializesFromLibrary('Time::TimeInstantValue')
kind = TriggerKind::when implies
    argument->notEmpty() and
    argument->at(1).oclIsKindOf(FeatureReferenceExpression) and
    let referent : Feature = 
        argument->at(1).oclAsType(FeatureReferenceExpression).referent in
    referent.oclIsKindOf(Expression) and
    referent.oclAsType(Expression).result.specializesFromLibrary('ScalarValues::Boolean')"""
    kind = EAttribute(eType=TriggerKind, unique=True, derived=False, changeable=True)

    def __init__(self, *, kind=None, **kwargs):

        super().__init__(**kwargs)

        if kind is not None:
            self.kind = kind


class DerivedExposedelement(EDerivedCollection):
    pass


class DerivedSatisfiedviewpoint(EDerivedCollection):
    pass


class DerivedViewcondition(EDerivedCollection):
    pass


class ViewUsage(PartUsage):
    """<p>A <code>ViewUsage</code> is a usage of a <code>ViewDefinition</code> to specify the generation of a view of the <code>members</code> of a collection of <code>exposedNamespaces</code>. The <code>ViewUsage</code> can satisfy more <code>viewpoints</code> than its definition, and it can specialize the <code>viewRendering</code> specified by its definition.<p>
exposedElement = ownedImport->selectByKind(Expose).
    importedMemberships(Set{}).memberElement->
    select(elm | includeAsExposed(elm))->
    asOrderedSet()
satisfiedViewpoint = ownedRequirement->
    selectByKind(ViewpointUsage)->
    select(isComposite)
viewCondition = ownedMembership->
    selectByKind(ElementFilterMembership).
    condition
viewRendering =
    let renderings: OrderedSet(ViewRenderingMembership) =
        featureMembership->selectByKind(ViewRenderingMembership) in
    if renderings->isEmpty() then null
    else renderings->first().referencedRendering
    endif
featureMembership->
    selectByKind(ViewRenderingMembership)->
    size() <= 1
specializesFromLibrary('Views::views')
owningType <> null and
(owningType.oclIsKindOf(ViewDefinition) or
 owningType.oclIsKindOf(ViewUsage)) implies
    specializesFromLibrary('Views::View::subviews')"""
    exposedElement = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedExposedelement)
    satisfiedViewpoint = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedSatisfiedviewpoint)
    viewCondition = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedViewcondition)
    _viewDefinition = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='viewDefinition', transient=True)
    _viewRendering = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='viewRendering', transient=True)

    @property
    def viewDefinition(self):
        raise NotImplementedError('Missing implementation for viewDefinition')

    @viewDefinition.setter
    def viewDefinition(self, value):
        raise NotImplementedError('Missing implementation for viewDefinition')

    @property
    def viewRendering(self):
        raise NotImplementedError('Missing implementation for viewRendering')

    @viewRendering.setter
    def viewRendering(self, value):
        raise NotImplementedError('Missing implementation for viewRendering')

    def __init__(self, *, exposedElement=None, satisfiedViewpoint=None, viewCondition=None, viewDefinition=None, viewRendering=None, **kwargs):

        super().__init__(**kwargs)

        if exposedElement:
            self.exposedElement.extend(exposedElement)

        if satisfiedViewpoint:
            self.satisfiedViewpoint.extend(satisfiedViewpoint)

        if viewCondition:
            self.viewCondition.extend(viewCondition)

        if viewDefinition is not None:
            self.viewDefinition = viewDefinition

        if viewRendering is not None:
            self.viewRendering = viewRendering

    def includeAsExposed(self, element=None):
        """<p>Determine whether the given <code>element</code> meets all the owned and inherited <code>viewConditions</code>.</p>
let metadataFeatures: Sequence(AnnotatingElement) = 
    element.ownedAnnotation.annotatingElement->
        select(oclIsKindOf(MetadataFeature)) in
self.membership->selectByKind(ElementFilterMembership).
    condition->forAll(cond | 
        metadataFeatures->exists(elem | 
            cond.checkCondition(elem)))"""
        raise NotImplementedError('operation includeAsExposed(...) not yet implemented')


class BindingConnectorAsUsage(ConnectorAsUsage, BindingConnector):
    """<p>A <code>BindingConnectorAsUsage</code> is both a <code>BindingConnector</code> and a <code>ConnectorAsUsage</code>.</p>"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class CalculationUsage(ActionUsage, Expression):
    """<p>A <code>CalculationUsage</code> is an <code>ActionUsage</code> that is also an <code>Expression</code>, and, so, is typed by a <code>Function</code>. Nominally, if the <code>type</code> is a <code>CalculationDefinition</code>, a <code>CalculationUsage</code> is a <code>Usage</code> of that <code>CalculationDefinition</code> within a system. However, other kinds of kernel <code>Functions</code> are also allowed, to permit use of <code>Functions</code> from the Kernel Model Libraries.</p>
specializesFromLibrary('Calculations::calculations')
owningType <> null and
(owningType.oclIsKindOf(CalculationDefinition) or
 owningType.oclIsKindOf(CalculationUsage)) implies
    specializesFromLibrary('Calculations::Calculation::subcalculations')"""
    _calculationDefinition = EReference(
        ordered=True, unique=True, containment=False, derived=True, name='calculationDefinition', transient=True)

    @property
    def calculationDefinition(self):
        raise NotImplementedError('Missing implementation for calculationDefinition')

    @calculationDefinition.setter
    def calculationDefinition(self, value):
        raise NotImplementedError('Missing implementation for calculationDefinition')

    def __init__(self, *, calculationDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if calculationDefinition is not None:
            self.calculationDefinition = calculationDefinition


class CollectExpression(OperatorExpression):
    """<p>A <code>CollectExpression</code> is an <code>OperatorExpression</code> whose <code>operator</code> is <code>"collect"</code>, which resolves to the <code>Function</code> <em><code>ControlFunctions::collect</code></em> from the Kernel Functions Library.</p>
operator = 'collect'"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class ConjugatedPortDefinition(PortDefinition):
    """<p>A <code>ConjugatedPortDefinition</code> is a <code>PortDefinition</code> that is a <code>PortDefinition</code> of its original <code>PortDefinition</code>. That is, a <code>ConjugatedPortDefinition</code> inherits all the <code>features</code> of the original <code>PortDefinition</code>, but input <code>flows</code> of the original <code>PortDefinition</code> become outputs on the <code>ConjugatedPortDefinition</code> and output <code>flows</code> of the original <code>PortDefinition</code> become inputs on the <code>ConjugatedPortDefinition</code>. Every <code>PortDefinition</code> (that is not itself a <code><code>ConjugatedPortDefinition</code></code>) has exactly one corresponding <code>ConjugatedPortDefinition</code>, whose effective name is the name of the <code>originalPortDefinition</code>, with the character <code>~</code> prepended.</p>
ownedPortConjugator.originalPortDefinition = originalPortDefinition
conjugatedPortDefinition = null"""
    _originalPortDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='originalPortDefinition', transient=True)
    _ownedPortConjugator = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='ownedPortConjugator', transient=True)

    @property
    def originalPortDefinition(self):
        raise NotImplementedError('Missing implementation for originalPortDefinition')

    @originalPortDefinition.setter
    def originalPortDefinition(self, value):
        raise NotImplementedError('Missing implementation for originalPortDefinition')

    @property
    def ownedPortConjugator(self):
        raise NotImplementedError('Missing implementation for ownedPortConjugator')

    @ownedPortConjugator.setter
    def ownedPortConjugator(self, value):
        raise NotImplementedError('Missing implementation for ownedPortConjugator')

    def __init__(self, *, originalPortDefinition=None, ownedPortConjugator=None, **kwargs):

        super().__init__(**kwargs)

        if originalPortDefinition is not None:
            self.originalPortDefinition = originalPortDefinition

        if ownedPortConjugator is not None:
            self.ownedPortConjugator = ownedPortConjugator


class ConstraintUsage(OccurrenceUsage, BooleanExpression):
    """<p>A <code>ConstraintUsage</code> is an <code>OccurrenceUsage</code> that is also a <code>BooleanExpression</code>, and, so, is typed by a <code>Predicate</code>. Nominally, if the type is a <code>ConstraintDefinition</code>, a <code>ConstraintUsage</code> is a <code>Usage</code> of that <code>ConstraintDefinition</code>. However, other kinds of kernel <code>Predicates</code> are also allowed, to permit use of <code>Predicates</code> from the Kernel Model Libraries.</p>
isComposite and
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(RequirementConstraintMembership) implies
    if owningFeatureMembership.oclAsType(RequirementConstraintMembership).kind = 
        RequirementConstraintKind::assumption then
        specializesFromLibrary('Requirements::RequirementCheck::assumptions')
    else
        specializesFromLibrary('Requirements::RequirementCheck::constraints')
    endif
specializesFromLibrary('Constraints::constraintChecks')
owningType <> null and
(owningType.oclIsKindOf(ItemDefinition) or
 owningType.oclIsKindOf(ItemUsage)) implies
    specializesFromLibrary('Items::Item::checkedConstraints')"""
    _constraintDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='constraintDefinition', transient=True)

    @property
    def constraintDefinition(self):
        raise NotImplementedError('Missing implementation for constraintDefinition')

    @constraintDefinition.setter
    def constraintDefinition(self, value):
        raise NotImplementedError('Missing implementation for constraintDefinition')

    def __init__(self, *, constraintDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if constraintDefinition is not None:
            self.constraintDefinition = constraintDefinition


class DecisionNode(ControlNode):
    """<p>A <code>DecisionNode</code> is a <code>ControlNode</code> that makes a selection from its outgoing <code>Successions</code>.</p>
targetConnector->selectByKind(Succession)->size() <= 1
sourceConnector->selectAsKind(Succession)->
    collect(connectorEnd->at(2))->
    forAll(targetMult |
        multiplicityHasBounds(targetMult, 0, 1))
specializesFromLibrary('Actions::Action::decisions')
sourceConnector->selectByKind(Succession)->
    forAll(subsetsChain(self, 
        resolveGlobal('ControlPerformances::DecisionPerformance::outgoingHBLink')))"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class FeatureChainExpression(OperatorExpression):
    """<p>A <code>FeatureChainExpression</code> is an <code>OperatorExpression</code> whose operator is <code>"."</code>, which resolves to the <code>Function</code> <em><code>ControlFunctions::'.'</code></em> from the Kernel Functions Library. It evaluates to the result of chaining the <code>result</code> <code>Feature</code> of its single <code>argument</code> <code>Expression</code> with its <code>targetFeature</code>.</p>
let sourceTargetFeature : Feature = sourceTargetFeature() in
sourceTargetFeature <> null and
sourceTargetFeature.redefinesFromLibrary('ControlFunctions::\'.\'::source::target')
let sourceTargetFeature : Feature = sourceTargetFeature() in
sourceTargetFeature <> null and
sourceTargetFeature.redefines(targetFeature)
targetFeature =
    let nonParameterMemberships : Sequence(Membership) = ownedMembership->
        reject(oclIsKindOf(ParameterMembership)) in
    if nonParameterMemberships->isEmpty() or
       not nonParameterMemberships->first().memberElement.oclIsKindOf(Feature)
    then null
    else nonParameterMemberships->first().memberElement.oclAsType(Feature)
    endif
argument->notEmpty() implies
    targetFeature.isFeaturedWithin(argument->first().result)
operator = '.'
let inputParameters : Sequence(Feature) = 
    ownedFeatures->select(direction = _'in') in
let sourceTargetFeature : Feature = 
    owningExpression.sourceTargetFeature() in
sourceTargetFeature <> null and
result.subsetsChain(inputParameters->first(), sourceTargetFeature) and
result.owningType = self"""
    _targetFeature = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='targetFeature', transient=True)

    @property
    def targetFeature(self):
        raise NotImplementedError('Missing implementation for targetFeature')

    @targetFeature.setter
    def targetFeature(self, value):
        raise NotImplementedError('Missing implementation for targetFeature')

    def __init__(self, *, targetFeature=None, **kwargs):

        super().__init__(**kwargs)

        if targetFeature is not None:
            self.targetFeature = targetFeature

    def sourceTargetFeature(self):
        """<p>Return the first <code>ownedFeature</code> of the first owned input <code>parameter</code> of this <code>FeatureChainExpression</code> (if any).</p>
let inputParameters : Feature = ownedFeatures->
    select(direction = _'in') in
if inputParameters->isEmpty() or 
   inputParameters->first().ownedFeature->isEmpty()
then null
else inputParameters->first().ownedFeature->first()
endif"""
        raise NotImplementedError('operation sourceTargetFeature(...) not yet implemented')


class ForLoopActionUsage(LoopActionUsage):
    """<p>A <code>ForLoopActionUsage</code> is a <code>LoopActionUsage</code> that specifies that its <code>bodyAction</code> <code>ActionUsage</code> should be performed once for each value, in order, from the sequence of values obtained as the result of the <code>seqArgument</code> <code>Expression</code>, with the <code>loopVariable</code> set to the value for each iteration.</p>
seqArgument = argument(1)

isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::forLoops')
loopVariable <> null and
loopVariable.redefinesFromLibrary('Actions::ForLoopAction::var')
specializesFromLibrary('Actions::forLoopActions')
loopVariable =
    if ownedFeature->isEmpty() or 
        not ownedFeature->first().oclIsKindOf(ReferenceUsage) then 
        null
    else 
        ownedFeature->first().oclAsType(ReferenceUsage)
    endif
ownedFeature->notEmpty() and
ownedFeature->at(1).oclIsKindOf(ReferenceUsage)

inputParameters()->size() = 2"""
    _loopVariable = EReference(ordered=False, unique=True, containment=False,
                               derived=True, name='loopVariable', transient=True)
    _seqArgument = EReference(ordered=False, unique=True, containment=False,
                              derived=True, name='seqArgument', transient=True)

    @property
    def loopVariable(self):
        raise NotImplementedError('Missing implementation for loopVariable')

    @loopVariable.setter
    def loopVariable(self, value):
        raise NotImplementedError('Missing implementation for loopVariable')

    @property
    def seqArgument(self):
        raise NotImplementedError('Missing implementation for seqArgument')

    @seqArgument.setter
    def seqArgument(self, value):
        raise NotImplementedError('Missing implementation for seqArgument')

    def __init__(self, *, loopVariable=None, seqArgument=None, **kwargs):

        super().__init__(**kwargs)

        if loopVariable is not None:
            self.loopVariable = loopVariable

        if seqArgument is not None:
            self.seqArgument = seqArgument


class ForkNode(ControlNode):
    """<p>A <code>ForkNode</code> is a <code>ControlNode</code> that must be followed by successor <code>Actions</code> as given by all its outgoing <code>Successions</code>.</p>
targetConnector->selectByKind(Succession)->size() <= 1
specializesFromLibrary('Actions::Action::forks')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class IndexExpression(OperatorExpression):
    """<p>An <code>IndexExpression</code> is an <code>OperatorExpression</code> whose operator is <code>"#"</code>, which resolves to the <code>Function</code> <em><code>BasicFunctions::'#'</code></em> from the Kernel Functions Library.</p>
arguments->notEmpty() and 
not arguments->first().result.specializesFromLibrary('Collections::Array') implies
    result.specializes(arguments->first().result)
operator = '#'"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class JoinNode(ControlNode):
    """<p>A <code>JoinNode</code> is a <code>ControlNode</code> that waits for the completion of all the predecessor <code>Actions</code> given by incoming <code>Successions</code>.</p>
sourceConnector->selectByKind(Succession)->size() <= 1
specializesFromLibrary('Actions::Action::join')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class MergeNode(ControlNode):
    """<p>A <code>MergeNode</code> is a <code>ControlNode</code> that asserts the merging of its incoming <code>Successions</code>. A <code>MergeNode</code> may have at most one outgoing <code>Successions</code>.</p>
sourceConnector->selectAsKind(Succession)->size() <= 1
targetConnector->selectByKind(Succession)->
    collect(connectorEnd->at(1))->
    forAll(sourceMult |
        multiplicityHasBounds(sourceMult, 0, 1))
targetConnector->selectByKind(Succession)->
    forAll(subsetsChain(self, 
        resolveGlobal('ControlPerformances::MergePerformance::incomingHBLink')))
specializesFromLibrary('Actions::Action::merges')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class MetadataUsage(ItemUsage, MetadataFeature):
    """<p>A  <code>MetadataUsage</code> is a <code>Usage</code> and a <code>MetadataFeature</code>, used to annotate other <code>Elements</code> in a system model with metadata. As a <code>MetadataFeature</code>, its type must be a <code>Metaclass</code>, which will nominally be a <code>MetadataDefinition</code>. However, any kernel <code>Metaclass</code> is also allowed, to permit use of <code>Metaclasses</code> from the Kernel Model Libraries.</p>
specializesFromLibrary('Metadata::metadataItems')"""
    _metadataDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='metadataDefinition', transient=True)

    @property
    def metadataDefinition(self):
        raise NotImplementedError('Missing implementation for metadataDefinition')

    @metadataDefinition.setter
    def metadataDefinition(self, value):
        raise NotImplementedError('Missing implementation for metadataDefinition')

    def __init__(self, *, metadataDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if metadataDefinition is not None:
            self.metadataDefinition = metadataDefinition


class PartDefinition(ItemDefinition):
    """<p>A <code>PartDefinition</code> is an <code>ItemDefinition</code> of a <code>Class</code> of systems or parts of systems. Note that all parts may be considered items for certain purposes, but not all items are parts that can perform actions within a system.</p>

specializesFromLibrary('Parts::Part')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class PerformActionUsage(ActionUsage, EventOccurrenceUsage):
    """<p>A <code>PerformActionUsage</code> is an <code>ActionUsage</code> that represents the performance of an <code>ActionUsage</code>. Unless it is the <code>PerformActionUsage</code> itself, the <code>ActionUsage</code> to be performed is related to the <code>PerformActionUsage</code> by a <code>ReferenceSubsetting</code> relationship. A <code>PerformActionUsage</code> is also an <code>EventOccurrenceUsage</code>, with its <code>performedAction</code> as the <code>eventOccurrence</code>.</p>
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(ActionUsage)
owningType <> null and
(owningType.oclIsKindOf(PartDefinition) or
 owningType.oclIsKindOf(PartUsage)) implies
    specializesFromLibrary('Parts::Part::performedActions')"""
    _performedAction = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='performedAction', transient=True)

    @property
    def performedAction(self):
        raise NotImplementedError('Missing implementation for performedAction')

    @performedAction.setter
    def performedAction(self, value):
        raise NotImplementedError('Missing implementation for performedAction')

    def __init__(self, *, performedAction=None, **kwargs):

        super().__init__(**kwargs)

        if performedAction is not None:
            self.performedAction = performedAction

    @operation
    def evaluate(self, runtime: RuntimeState):

        # Resolve which ActionDef this call performs (e.g. pEntry -> Print),
        # via the registry Namespace.evaluate() already built.
        target = _feature_type(self)
        action_def = next(
            (element for element in runtime.elements
             if isinstance(element, rt.ActionDef) and element.definition is target),
            None,
        )

        # Bind each argument (e.g. msg="Entry") to the formal parameter it
        # fulfills, if the target ActionDef and a matching formal are known.
        # No side effect: what "performing" an action does isn't defined by
        # the model for a bodyless leaf action like Print, so this only
        # resolves and returns the bound parameters.
        bound = []
        for feature in _owned_by_kind(self, FeatureMembership):
            name = feature.declaredName
            if name is None:
                continue
            formal = None
            if action_def is not None:
                formal = next(
                    (parameter for parameter in action_def.parameters if parameter.qualified_name == name),
                    None,
                )
            bound.append(rt.Parameter(
                qualified_name=name,
                type=formal,
                value=_bound_value(feature),
            ))

        return bound


class SelectExpression(OperatorExpression):
    """<p>A <code>SelectExpression</code> is an <code>OperatorExpression</code> whose operator is <code>"select"</code>, which resolves to the <code>Function</code> <em><code>ControlFunctions::select</code></em> from the Kernel Functions Library.</p>
operator = 'select'
arguments->notEmpty() implies
    result.specializes(arguments->first().result)"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedState(EDerivedCollection):
    pass


class StateDefinition(ActionDefinition):
    """<p>A <code>StateDefinition</code> is the <code>Definition</code> of the </code>Behavior</code> of a system or part of a system in a certain state condition.</p>

<p>A <code>StateDefinition</code> may be related to up to three of its <code>ownedFeatures</code> by <code>StateBehaviorMembership</code> <code>Relationships</code>, all of different <code>kinds</code>, corresponding to the entry, do and exit actions of the <code>StateDefinition</code>.</p>
specializesFromLibrary('States::StateAction')
ownedMembership->
    selectByKind(StateSubactionMembership)->
    isUnique(kind)
state = action->selectByKind(StateUsage)
doAction =
    let doMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::do) in
    if doMemberships->isEmpty() then null
    else doMemberships->at(1)
    endif
entryAction =
    let entryMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::entry) in
    if entryMemberships->isEmpty() then null
    else entryMemberships->at(1)
    endif
isParallel implies
    ownedAction.incomingTransition->isEmpty() and
    ownedAction.outgoingTransition->isEmpty()
exitAction = 
    let exitMemberships : Sequence(StateSubactionMembership) =
        ownedMembership->
            selectByKind(StateSubactionMembership)->
            select(kind = StateSubactionKind::exit) in
    if exitMemberships->isEmpty() then null
    else exitMemberships->at(1)
    endif"""
    isParallel = EAttribute(eType=EBoolean, unique=True, derived=False,
                            changeable=True, default_value=False)
    _doAction = EReference(ordered=False, unique=True, containment=False,
                           derived=True, name='doAction', transient=True)
    _entryAction = EReference(ordered=False, unique=True, containment=False,
                              derived=True, name='entryAction', transient=True)
    _exitAction = EReference(ordered=False, unique=True, containment=False,
                             derived=True, name='exitAction', transient=True)
    state = EReference(ordered=True, unique=True, containment=False, derived=True,
                       upper=-1, transient=True, derived_class=DerivedState)

    @property
    def doAction(self):
        raise NotImplementedError('Missing implementation for doAction')

    @doAction.setter
    def doAction(self, value):
        raise NotImplementedError('Missing implementation for doAction')

    @property
    def entryAction(self):
        raise NotImplementedError('Missing implementation for entryAction')

    @entryAction.setter
    def entryAction(self, value):
        raise NotImplementedError('Missing implementation for entryAction')

    @property
    def exitAction(self):
        raise NotImplementedError('Missing implementation for exitAction')

    @exitAction.setter
    def exitAction(self, value):
        raise NotImplementedError('Missing implementation for exitAction')

    def __init__(self, *, doAction=None, entryAction=None, exitAction=None, isParallel=None, state=None, **kwargs):

        super().__init__(**kwargs)

        if isParallel is not None:
            self.isParallel = isParallel

        if doAction is not None:
            self.doAction = doAction

        if entryAction is not None:
            self.entryAction = entryAction

        if exitAction is not None:
            self.exitAction = exitAction

        if state:
            self.state.extend(state)


class SuccessionAsUsage(ConnectorAsUsage, Succession):
    """<p>A <code>SuccessionAsUsage</code> is both a <code>ConnectorAsUsage</code> and a <code>Succession</code>.<p>"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class SuccessionFlow(Flow, Succession):
    """<p>A <code>SuccessionFlow</code> is a <code>Flow</code> that also provides temporal ordering. It classifies <code><em>Transfers</em></code> that cannot start until the source <code><em>Occurrence</em></code> has completed and that must complete before the target <code><em>Occurrence</em></code> can start.</p>
specializesFromLibrary('Transfers::flowTransfersBefore')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class WhileLoopActionUsage(LoopActionUsage):
    """<p>A <code>WhileLoopActionUsage</code> is a <code>LoopActionUsage</code> that specifies that the <code>bodyAction</code> <code>ActionUsage</code> should be performed repeatedly while the result of the <code>whileArgument</code> <code>Expression</code> is true or until the result of the <code>untilArgument</code> <code>Expression</code> (if provided) is true. The <code>whileArgument</code> <code>Expression</code> is evaluated before each (possible) performance of the <code>bodyAction</code>, and the <code>untilArgument</code> <code>Expression</code> is evaluated after each performance of the <code>bodyAction</code>.</p>
isSubactionUsage() implies
    specializesFromLibrary('Actions::Action::whileLoops')
untilArgument =
    let parameter : Feature = inputParameter(3) in
    if parameter <> null and parameter.oclIsKindOf(Expression) then
        parameter.oclAsType(Expression)
    else
        null
    endif

specializesFromLibrary('Actions::whileLoopActions')
whileArgument =
    let parameter : Feature = inputParameter(1) in
    if parameter <> null and parameter.oclIsKindOf(Expression) then
        parameter.oclAsType(Expression)
    else
        null
    endif

inputParameters()->size() >= 2"""
    _untilArgument = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='untilArgument', transient=True)
    _whileArgument = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='whileArgument', transient=True)

    @property
    def untilArgument(self):
        raise NotImplementedError('Missing implementation for untilArgument')

    @untilArgument.setter
    def untilArgument(self, value):
        raise NotImplementedError('Missing implementation for untilArgument')

    @property
    def whileArgument(self):
        raise NotImplementedError('Missing implementation for whileArgument')

    @whileArgument.setter
    def whileArgument(self, value):
        raise NotImplementedError('Missing implementation for whileArgument')

    def __init__(self, *, untilArgument=None, whileArgument=None, **kwargs):

        super().__init__(**kwargs)

        if untilArgument is not None:
            self.untilArgument = untilArgument

        if whileArgument is not None:
            self.whileArgument = whileArgument


class DerivedCalculation(EDerivedCollection):
    pass


class CalculationDefinition(ActionDefinition, Function):
    """<p>A <code>CalculationDefinition</code> is an <coed>ActionDefinition</code> that also defines a <code>Function</code> producing a <code>result</code>.</p>
specializesFromLibrary('Calculations::Calculation')
calculation = action->selectByKind(CalculationUsage)"""
    calculation = EReference(ordered=True, unique=True, containment=False,
                             derived=True, upper=-1, transient=True, derived_class=DerivedCalculation)

    def __init__(self, *, calculation=None, **kwargs):

        super().__init__(**kwargs)

        if calculation:
            self.calculation.extend(calculation)


class DerivedActorparameter(EDerivedCollection):
    pass


class CaseUsage(CalculationUsage):
    """<p>A <code>CaseUsage</code> is a <code>Usage</code> of a <code>CaseDefinition</code>.</p>
objectiveRequirement = 
    let objectives: OrderedSet(RequirementUsage) = 
        featureMembership->
            selectByKind(ObjectiveMembership).
            ownedRequirement in
    if objectives->isEmpty() then null
    else objectives->first().ownedObjectiveRequirement
    endif
featureMembership->
    selectByKind(ObjectiveMembership)->
    size() <= 1
featureMembership->
        selectByKind(SubjectMembership)->
        size() <= 1
actorParameter = featureMembership->
    selectByKind(ActorMembership).
    ownedActorParameter
subjectParameter =
    let subjects : OrderedSet(SubjectMembership) = 
        featureMembership->selectByKind(SubjectMembership) in
    if subjects->isEmpty() then null
    else subjects->first().ownedSubjectParameter
    endif
input->notEmpty() and input->first() = subjectParameter
specializesFromLibrary('Cases::cases')
isComposite and owningType <> null and 
    (owningType.oclIsKindOf(CaseDefinition) or
     owningType.oclIsKindOf(CaseUsage)) implies
    specializesFromLibrary('Cases::Case::subcases')"""
    actorParameter = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedActorparameter)
    _caseDefinition = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='caseDefinition', transient=True)
    _objectiveRequirement = EReference(
        ordered=True, unique=True, containment=False, derived=True, name='objectiveRequirement', transient=True)
    _subjectParameter = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='subjectParameter', transient=True)

    @property
    def caseDefinition(self):
        raise NotImplementedError('Missing implementation for caseDefinition')

    @caseDefinition.setter
    def caseDefinition(self, value):
        raise NotImplementedError('Missing implementation for caseDefinition')

    @property
    def objectiveRequirement(self):
        raise NotImplementedError('Missing implementation for objectiveRequirement')

    @objectiveRequirement.setter
    def objectiveRequirement(self, value):
        raise NotImplementedError('Missing implementation for objectiveRequirement')

    @property
    def subjectParameter(self):
        raise NotImplementedError('Missing implementation for subjectParameter')

    @subjectParameter.setter
    def subjectParameter(self, value):
        raise NotImplementedError('Missing implementation for subjectParameter')

    def __init__(self, *, actorParameter=None, caseDefinition=None, objectiveRequirement=None, subjectParameter=None, **kwargs):

        super().__init__(**kwargs)

        if actorParameter:
            self.actorParameter.extend(actorParameter)

        if caseDefinition is not None:
            self.caseDefinition = caseDefinition

        if objectiveRequirement is not None:
            self.objectiveRequirement = objectiveRequirement

        if subjectParameter is not None:
            self.subjectParameter = subjectParameter


class ConstraintDefinition(OccurrenceDefinition, Predicate):
    """<p>A <code>ConstraintDefinition</code> is an <code>OccurrenceDefinition</code> that is also a <code>Predicate</code> that defines a constraint that may be asserted to hold on a system or part of a system.</p>


specializesFromLibrary('Constraints::ConstraintCheck')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class MetadataDefinition(ItemDefinition, Metaclass):
    """<p>A <code>MetadataDefinition</code> is an <code>ItemDefinition</code> that is also a <code>Metaclass</code>.</p>
specializesFromLibrary('Metadata::MetadataItem')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedRendering(EDerivedCollection):
    pass


class RenderingDefinition(PartDefinition):
    """<p>A <code>RenderingDefinition</code> is a <code>PartDefinition</code> that defines a specific rendering of the content of a model view (e.g., symbols, style, layout, etc.).</p>
rendering = usages->selectByKind(RenderingUsage)
specializesFromLibrary('Views::Rendering')"""
    rendering = EReference(ordered=True, unique=True, containment=False,
                           derived=True, upper=-1, transient=True, derived_class=DerivedRendering)

    def __init__(self, *, rendering=None, **kwargs):

        super().__init__(**kwargs)

        if rendering:
            self.rendering.extend(rendering)


class DerivedActorparameter(EDerivedCollection):
    pass


class DerivedAssumedconstraint(EDerivedCollection):
    pass


class DerivedFramedconcern(EDerivedCollection):
    pass


class DerivedRequiredconstraint(EDerivedCollection):
    pass


class DerivedStakeholderparameter(EDerivedCollection):
    pass


class DerivedText(EDerivedCollection):
    pass


class RequirementUsage(ConstraintUsage):
    """<p>A <code>RequirementUsage</code> is a <code>Usage</code> of a <code>RequirementDefinition</code>.</p>
actorParameter = featureMembership->
    selectByKind(ActorMembership).
    ownedActorParameter
assumedConstraint = ownedFeatureMembership->
    selectByKind(RequirementConstraintMembership)->
    select(kind = RequirementConstraintKind::assumption).
    ownedConstraint
framedConcern = featureMembership->
    selectByKind(FramedConcernMembership).
    ownedConcern
requiredConstraint = ownedFeatureMembership->
    selectByKind(RequirementConstraintMembership)->
    select(kind = RequirementConstraintKind::requirement).
    ownedConstraint
stakeholderParameter = featureMembership->
    selectByKind(AStakholderMembership).
    ownedStakeholderParameter
subjectParameter =
    let subjects : OrderedSet(SubjectMembership) = 
        featureMembership->selectByKind(SubjectMembership) in
    if subjects->isEmpty() then null
    else subjects->first().ownedSubjectParameter
    endif
text = documentation.body
featureMembership->
    selectByKind(SubjectMembership)->
    size() <= 1
input->notEmpty() and input->first() = subjectParameter
specializesFromLibrary('Requirements::requirementChecks')
isComposite and owningType <> null and
    (owningType.oclIsKindOf(RequirementDefinition) or
     owningType.oclIsKindOf(RequirementUsage)) implies
    specializesFromLibrary('Requirements::RequirementCheck::subrequirements')
owningfeatureMembership <> null and
owningfeatureMembership.oclIsKindOf(ObjectiveMembership) implies
    owningType.ownedSpecialization.general->forAll(gen |
        (gen.oclIsKindOf(CaseDefinition) implies
            redefines(gen.oclAsType(CaseDefinition).objectiveRequirement)) and
        (gen.oclIsKindOf(Feature) and 
         gen.oclAsType(Feature).featureTarget.oclIsKindOf(CaseUsage) implies
            redefines(gen.oclAsType(Feature).featureTarget.
                        oclAsType(CaseUsage).objectiveRequirement))
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(RequirementVerificationMembership) implies
    specializesFromLibrary('VerificationCases::VerificationCase::obj::requirementVerifications')"""
    reqId = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    text = EAttribute(eType=EString, unique=True, derived=True, changeable=True,
                      upper=-1, transient=True, derived_class=DerivedText)
    actorParameter = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedActorparameter)
    assumedConstraint = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedAssumedconstraint)
    framedConcern = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedFramedconcern)
    requiredConstraint = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedRequiredconstraint)
    _requirementDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='requirementDefinition', transient=True)
    stakeholderParameter = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedStakeholderparameter)
    _subjectParameter = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='subjectParameter', transient=True)

    @property
    def requirementDefinition(self):
        raise NotImplementedError('Missing implementation for requirementDefinition')

    @requirementDefinition.setter
    def requirementDefinition(self, value):
        raise NotImplementedError('Missing implementation for requirementDefinition')

    @property
    def subjectParameter(self):
        raise NotImplementedError('Missing implementation for subjectParameter')

    @subjectParameter.setter
    def subjectParameter(self, value):
        raise NotImplementedError('Missing implementation for subjectParameter')

    def __init__(self, *, actorParameter=None, assumedConstraint=None, framedConcern=None, reqId=None, requiredConstraint=None, requirementDefinition=None, stakeholderParameter=None, subjectParameter=None, text=None, **kwargs):

        super().__init__(**kwargs)

        if reqId is not None:
            self.reqId = reqId

        if text:
            self.text.extend(text)

        if actorParameter:
            self.actorParameter.extend(actorParameter)

        if assumedConstraint:
            self.assumedConstraint.extend(assumedConstraint)

        if framedConcern:
            self.framedConcern.extend(framedConcern)

        if requiredConstraint:
            self.requiredConstraint.extend(requiredConstraint)

        if requirementDefinition is not None:
            self.requirementDefinition = requirementDefinition

        if stakeholderParameter:
            self.stakeholderParameter.extend(stakeholderParameter)

        if subjectParameter is not None:
            self.subjectParameter = subjectParameter


class DerivedSatisfiedviewpoint(EDerivedCollection):
    pass


class DerivedView(EDerivedCollection):
    pass


class DerivedViewcondition(EDerivedCollection):
    pass


class ViewDefinition(PartDefinition):
    """<p>A <code>ViewDefinition</code> is a <code>PartDefinition</code> that specifies how a view artifact is constructed to satisfy a <code>viewpoint</code>. It specifies a <code>viewConditions</code> to define the model content to be presented and a <code>viewRendering</code> to define how the model content is presented.</p>
view = usage->selectByKind(ViewUsage)
satisfiedViewpoint = ownedRequirement->
    selectByKind(ViewpointUsage)->
    select(isComposite)
viewRendering =
    let renderings: OrderedSet(ViewRenderingMembership) =
        featureMembership->selectByKind(ViewRenderingMembership) in
    if renderings->isEmpty() then null
    else renderings->first().referencedRendering
    endif
viewCondition = ownedMembership->
    selectByKind(ElementFilterMembership).
    condition
featureMembership->
    selectByKind(ViewRenderingMembership)->
    size() <= 1
specializesFromLibrary('Views::View')"""
    satisfiedViewpoint = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedSatisfiedviewpoint)
    view = EReference(ordered=True, unique=True, containment=False, derived=True,
                      upper=-1, transient=True, derived_class=DerivedView)
    viewCondition = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedViewcondition)
    _viewRendering = EReference(ordered=False, unique=True, containment=False,
                                derived=True, name='viewRendering', transient=True)

    @property
    def viewRendering(self):
        raise NotImplementedError('Missing implementation for viewRendering')

    @viewRendering.setter
    def viewRendering(self, value):
        raise NotImplementedError('Missing implementation for viewRendering')

    def __init__(self, *, satisfiedViewpoint=None, view=None, viewCondition=None, viewRendering=None, **kwargs):

        super().__init__(**kwargs)

        if satisfiedViewpoint:
            self.satisfiedViewpoint.extend(satisfiedViewpoint)

        if view:
            self.view.extend(view)

        if viewCondition:
            self.viewCondition.extend(viewCondition)

        if viewRendering is not None:
            self.viewRendering = viewRendering


class AnalysisCaseUsage(CaseUsage):
    """<p>An <code>AnalysisCaseUsage</code> is a <code>Usage</code> of an <code>AnalysisCaseDefinition</code>.</p>
resultExpression =
    let results : OrderedSet(ResultExpressionMembership) =
        featureMembersip->
            selectByKind(ResultExpressionMembership) in
    if results->isEmpty() then null
    else results->first().ownedResultExpression
    endif
specializesFromLibrary('AnalysisCases::analysisCases')
isComposite and owningType <> null and
    (owningType.oclIsKindOf(AnalysisCaseDefinition) or
     owningType.oclIsKindOf(AnalysisCaseUsage)) implies
    specializesFromLibrary('AnalysisCases::AnalysisCase::subAnalysisCases')"""
    _analysisCaseDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='analysisCaseDefinition', transient=True)
    _resultExpression = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='resultExpression', transient=True)

    @property
    def analysisCaseDefinition(self):
        raise NotImplementedError('Missing implementation for analysisCaseDefinition')

    @analysisCaseDefinition.setter
    def analysisCaseDefinition(self, value):
        raise NotImplementedError('Missing implementation for analysisCaseDefinition')

    @property
    def resultExpression(self):
        raise NotImplementedError('Missing implementation for resultExpression')

    @resultExpression.setter
    def resultExpression(self, value):
        raise NotImplementedError('Missing implementation for resultExpression')

    def __init__(self, *, analysisCaseDefinition=None, resultExpression=None, **kwargs):

        super().__init__(**kwargs)

        if analysisCaseDefinition is not None:
            self.analysisCaseDefinition = analysisCaseDefinition

        if resultExpression is not None:
            self.resultExpression = resultExpression


class AssertConstraintUsage(ConstraintUsage, Invariant):
    """<p>An <code>AssertConstraintUsage</code> is a <code>ConstraintUsage</code> that is also an <code>Invariant</code> and, so, is asserted to be true (by default). Unless it is the <code>AssertConstraintUsage</code> itself, the asserted <code>ConstraintUsage</code> is related to the <code>AssertConstraintUsage</code> by a ReferenceSubsetting <code>Relationship</code>.</p>
assertedConstraint =
    if referencedFeatureTarget() = null then self
    else if referencedFeatureTarget().oclIsKindOf(ConstraintUsage) then
        referencedFeatureTarget().oclAsType(ConstraintUsage)
    else null
    endif endif
if isNegated then
    specializesFromLibrary('Constraints::negatedConstraintChecks')
else
    specializesFromLibrary('Constraints::assertedConstraintChecks')
endif
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(ConstraintUsage)"""
    _assertedConstraint = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='assertedConstraint', transient=True)

    @property
    def assertedConstraint(self):
        raise NotImplementedError('Missing implementation for assertedConstraint')

    @assertedConstraint.setter
    def assertedConstraint(self, value):
        raise NotImplementedError('Missing implementation for assertedConstraint')

    def __init__(self, *, assertedConstraint=None, **kwargs):

        super().__init__(**kwargs)

        if assertedConstraint is not None:
            self.assertedConstraint = assertedConstraint


class DerivedActorparameter(EDerivedCollection):
    pass


class CaseDefinition(CalculationDefinition):
    """<p>A <code>CaseDefinition</code> is a <code>CalculationDefinition</code> for a process, often involving collecting evidence or data, relative to a subject, possibly involving the collaboration of one or more other actors, producing a result that meets an objective.</p>
objectiveRequirement = 
    let objectives: OrderedSet(RequirementUsage) = 
        featureMembership->
            selectByKind(ObjectiveMembership).
            ownedRequirement in
    if objectives->isEmpty() then null
    else objectives->first().ownedObjectiveRequirement
    endif
featureMembership->
    selectByKind(ObjectiveMembership)->
    size() <= 1
subjectParameter =
    let subjectMems : OrderedSet(SubjectMembership) = 
        featureMembership->selectByKind(SubjectMembership) in
    if subjectMems->isEmpty() then null
    else subjectMems->first().ownedSubjectParameter
    endif
actorParameter = featureMembership->
    selectByKind(ActorMembership).
    ownedActorParameter
featureMembership->selectByKind(SubjectMembership)->size() <= 1
input->notEmpty() and input->first() = subjectParameter
specializesFromLibrary('Cases::Case')"""
    actorParameter = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedActorparameter)
    _objectiveRequirement = EReference(
        ordered=True, unique=True, containment=False, derived=True, name='objectiveRequirement', transient=True)
    _subjectParameter = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='subjectParameter', transient=True)

    @property
    def objectiveRequirement(self):
        raise NotImplementedError('Missing implementation for objectiveRequirement')

    @objectiveRequirement.setter
    def objectiveRequirement(self, value):
        raise NotImplementedError('Missing implementation for objectiveRequirement')

    @property
    def subjectParameter(self):
        raise NotImplementedError('Missing implementation for subjectParameter')

    @subjectParameter.setter
    def subjectParameter(self, value):
        raise NotImplementedError('Missing implementation for subjectParameter')

    def __init__(self, *, actorParameter=None, objectiveRequirement=None, subjectParameter=None, **kwargs):

        super().__init__(**kwargs)

        if actorParameter:
            self.actorParameter.extend(actorParameter)

        if objectiveRequirement is not None:
            self.objectiveRequirement = objectiveRequirement

        if subjectParameter is not None:
            self.subjectParameter = subjectParameter


class ConcernUsage(RequirementUsage):
    """<p>A <code>ConcernUsage</code> is a <code>Usage</code> of a <code>ConcernDefinition</code>.</p>

 The <code>ownedStakeholder</code> features of the ConcernUsage shall all subset the <em><code>ConcernCheck::concernedStakeholders</code> </em>feature. If the ConcernUsage is an <code>ownedFeature</code> of a StakeholderDefinition or StakeholderUsage, then the ConcernUsage shall have an <code>ownedStakeholder</code> feature that is bound to the <em><code>self</code></em> feature of its owner.</p>

specializesFromLibrary('Requirements::concernChecks')
owningFeatureMembership <> null and
owningFeatureMembership.oclIsKindOf(FramedConcernMembership) implies
    specializesFromLibrary('Requirements::RequirementCheck::concerns')"""
    _concernDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='concernDefinition', transient=True)

    @property
    def concernDefinition(self):
        raise NotImplementedError('Missing implementation for concernDefinition')

    @concernDefinition.setter
    def concernDefinition(self, value):
        raise NotImplementedError('Missing implementation for concernDefinition')

    def __init__(self, *, concernDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if concernDefinition is not None:
            self.concernDefinition = concernDefinition


class DerivedConnectiondefinition(EDerivedCollection):
    pass


class ConnectionUsage(ConnectorAsUsage, PartUsage):
    """<p>A <code>ConnectionUsage</code> is a <code>ConnectorAsUsage</code> that is also a <code>PartUsage</code>. Nominally, if its type is a <code>ConnectionDefinition</code>, then a <code>ConnectionUsage</code> is a Usage of that <code>ConnectionDefinition</code>, representing a connection between parts of a system. However, other kinds of kernel <code>AssociationStructures</code> are also allowed, to permit use of <code>AssociationStructures</code> from the Kernel Model Libraries.</p>
specializesFromLibrary('Connections::connections')
ownedEndFeature->size() = 2 implies
    specializesFromLibrary('Connections::binaryConnections')"""
    connectionDefinition = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedConnectiondefinition)

    def __init__(self, *, connectionDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if connectionDefinition:
            self.connectionDefinition.extend(connectionDefinition)


class ExhibitStateUsage(StateUsage, PerformActionUsage):
    """<p>An <code>ExhibitStateUsage</code> is a <code>StateUsage</code> that represents the exhibiting of a <code>StateUsage</code>. Unless it is the <code>StateUsage</code> itself, the <code>StateUsage</code> to be exhibited is related to the <code>ExhibitStateUsage</code> by a <code>ReferenceSubsetting</code> <code>Relationship</code>. An <code>ExhibitStateUsage</code> is also a <code>PerformActionUsage</code>, with its <code>exhibitedState</code> as the <code>performedAction</code>.</p>

owningType <> null and
(owningType.oclIsKindOf(PartDefinition) or
 owningType.oclIsKindOf(PartUsage)) implies
    specializesFromLibrary('Parts::Part::exhibitedStates')
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(StateUsage)"""
    _exhibitedState = EReference(ordered=False, unique=True, containment=False,
                                 derived=True, name='exhibitedState', transient=True)

    @property
    def exhibitedState(self):
        raise NotImplementedError('Missing implementation for exhibitedState')

    @exhibitedState.setter
    def exhibitedState(self, value):
        raise NotImplementedError('Missing implementation for exhibitedState')

    def __init__(self, *, exhibitedState=None, **kwargs):

        super().__init__(**kwargs)

        if exhibitedState is not None:
            self.exhibitedState = exhibitedState


class DerivedActorparameter(EDerivedCollection):
    pass


class DerivedAssumedconstraint(EDerivedCollection):
    pass


class DerivedFramedconcern(EDerivedCollection):
    pass


class DerivedRequiredconstraint(EDerivedCollection):
    pass


class DerivedStakeholderparameter(EDerivedCollection):
    pass


class DerivedText(EDerivedCollection):
    pass


class RequirementDefinition(ConstraintDefinition):
    """<p>A <code>RequirementDefinition</code> is a <code>ConstraintDefinition</code> that defines a requirement used in the context of a specification as a constraint that a valid solution must satisfy. The specification is relative to a specified subject, possibly in collaboration with one or more external actors.</p>
text = documentation.body
assumedConstraint = ownedFeatureMembership->
    selectByKind(RequirementConstraintMembership)->
    select(kind = RequirementConstraintKind::assumption).
    ownedConstraint
requiredConstraint = ownedFeatureMembership->
    selectByKind(RequirementConstraintMembership)->
    select(kind = RequirementConstraintKind::requirement).
    ownedConstraint
subjectParameter =
    let subjects : OrderedSet(SubjectMembership) = 
        featureMembership->selectByKind(SubjectMembership) in
    if subjects->isEmpty() then null
    else subjects->first().ownedSubjectParameter
    endif
framedConcern = featureMembership->
    selectByKind(FramedConcernMembership).
    ownedConcern
actorParameter = featureMembership->
    selectByKind(ActorMembership).
    ownedActorParameter
stakeholderParameter = featureMembership->
    selectByKind(StakholderMembership).
    ownedStakeholderParameter
featureMembership->	
    selectByKind(SubjectMembership)->
    size() <= 1
input->notEmpty() and input->first() = subjectParameter
specializesFromLibrary('Requirements::RequirementCheck')"""
    reqId = EAttribute(eType=EString, unique=True, derived=False, changeable=True)
    text = EAttribute(eType=EString, unique=True, derived=True, changeable=True,
                      upper=-1, transient=True, derived_class=DerivedText)
    actorParameter = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedActorparameter)
    assumedConstraint = EReference(ordered=True, unique=True, containment=False,
                                   derived=True, upper=-1, transient=True, derived_class=DerivedAssumedconstraint)
    framedConcern = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedFramedconcern)
    requiredConstraint = EReference(ordered=True, unique=True, containment=False,
                                    derived=True, upper=-1, transient=True, derived_class=DerivedRequiredconstraint)
    stakeholderParameter = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedStakeholderparameter)
    _subjectParameter = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='subjectParameter', transient=True)

    @property
    def subjectParameter(self):
        raise NotImplementedError('Missing implementation for subjectParameter')

    @subjectParameter.setter
    def subjectParameter(self, value):
        raise NotImplementedError('Missing implementation for subjectParameter')

    def __init__(self, *, actorParameter=None, assumedConstraint=None, framedConcern=None, reqId=None, requiredConstraint=None, stakeholderParameter=None, subjectParameter=None, text=None, **kwargs):

        super().__init__(**kwargs)

        if reqId is not None:
            self.reqId = reqId

        if text:
            self.text.extend(text)

        if actorParameter:
            self.actorParameter.extend(actorParameter)

        if assumedConstraint:
            self.assumedConstraint.extend(assumedConstraint)

        if framedConcern:
            self.framedConcern.extend(framedConcern)

        if requiredConstraint:
            self.requiredConstraint.extend(requiredConstraint)

        if stakeholderParameter:
            self.stakeholderParameter.extend(stakeholderParameter)

        if subjectParameter is not None:
            self.subjectParameter = subjectParameter


class DerivedIncludedusecase(EDerivedCollection):
    pass


class UseCaseUsage(CaseUsage):
    """<p>A <code>UseCaseUsage</code> is a <code>Usage</code> of a <code>UseCaseDefinition</code>.</p>
includedUseCase = ownedUseCase->
    selectByKind(IncludeUseCaseUsage).
    useCaseIncluded
specializesFromLibrary('UseCases::useCases')
isComposite and owningType <> null and
(owningType.oclIsKindOf(UseCaseDefinition) or
 owningType.oclIsKindOf(UseCaseUsage)) implies
    specializesFromLibrary('UseCases::UseCase::subUseCases')"""
    includedUseCase = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedIncludedusecase)
    _useCaseDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='useCaseDefinition', transient=True)

    @property
    def useCaseDefinition(self):
        raise NotImplementedError('Missing implementation for useCaseDefinition')

    @useCaseDefinition.setter
    def useCaseDefinition(self, value):
        raise NotImplementedError('Missing implementation for useCaseDefinition')

    def __init__(self, *, includedUseCase=None, useCaseDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if includedUseCase:
            self.includedUseCase.extend(includedUseCase)

        if useCaseDefinition is not None:
            self.useCaseDefinition = useCaseDefinition


class DerivedVerifiedrequirement(EDerivedCollection):
    pass


class VerificationCaseUsage(CaseUsage):
    """<p>A <code>VerificationCaseUsage</code> is a </code>Usage</code> of a <code>VerificationCaseDefinition</code>.</p>
verifiedRequirement =
    if objectiveRequirement = null then OrderedSet{}
    else 
        objectiveRequirement.featureMembership->
            selectByKind(RequirementVerificationMembership).
            verifiedRequirement->asOrderedSet()
    endif
specializesFromLibrary('VerificationCases::verificationCases')
isComposite and owningType <> null and
    (owningType.oclIsKindOf(VerificationCaseDefinition) or
     owningType.oclIsKindOf(VerificationCaseUsage)) implies 
    specializesFromLibrary('VerificationCases::VerificationCase::subVerificationCases')"""
    _verificationCaseDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='verificationCaseDefinition', transient=True)
    verifiedRequirement = EReference(ordered=True, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedVerifiedrequirement)

    @property
    def verificationCaseDefinition(self):
        raise NotImplementedError('Missing implementation for verificationCaseDefinition')

    @verificationCaseDefinition.setter
    def verificationCaseDefinition(self, value):
        raise NotImplementedError('Missing implementation for verificationCaseDefinition')

    def __init__(self, *, verificationCaseDefinition=None, verifiedRequirement=None, **kwargs):

        super().__init__(**kwargs)

        if verificationCaseDefinition is not None:
            self.verificationCaseDefinition = verificationCaseDefinition

        if verifiedRequirement:
            self.verifiedRequirement.extend(verifiedRequirement)


class DerivedViewpointstakeholder(EDerivedCollection):
    pass


class ViewpointUsage(RequirementUsage):
    """<p>A <code>ViewpointUsage</code> is a <code>Usage</code> of a <code>ViewpointDefinition</code>.</p>


viewpointStakeholder = framedConcern.featureMemberhsip->
    selectByKind(StakeholderMembership).
    ownedStakeholderParameter
specializesFromLibrary('Views::viewpointChecks')
isComposite and owningType <> null and
(owningType.oclIsKindOf(ViewDefinition) or
 owningType.oclIsKindOf(ViewUsage)) implies
    specializesFromLibrary('Views::View::viewpointSatisfactions')"""
    _viewpointDefinition = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='viewpointDefinition', transient=True)
    viewpointStakeholder = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedViewpointstakeholder)

    @property
    def viewpointDefinition(self):
        raise NotImplementedError('Missing implementation for viewpointDefinition')

    @viewpointDefinition.setter
    def viewpointDefinition(self, value):
        raise NotImplementedError('Missing implementation for viewpointDefinition')

    def __init__(self, *, viewpointDefinition=None, viewpointStakeholder=None, **kwargs):

        super().__init__(**kwargs)

        if viewpointDefinition is not None:
            self.viewpointDefinition = viewpointDefinition

        if viewpointStakeholder:
            self.viewpointStakeholder.extend(viewpointStakeholder)


class DerivedAllocationdefinition(EDerivedCollection):
    pass


class AllocationUsage(ConnectionUsage):
    """<p>An <code>AllocationUsage</code> is a usage of an <code>AllocationDefinition</code> asserting the allocation of the <code>source</code> feature to the <code>target</code> feature.</p>
specializesFromLibrary('Allocations::allocations')"""
    allocationDefinition = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedAllocationdefinition)

    def __init__(self, *, allocationDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if allocationDefinition:
            self.allocationDefinition.extend(allocationDefinition)


class AnalysisCaseDefinition(CaseDefinition):
    """<p>An <code>AnalysisCaseDefinition</code> is a <code>CaseDefinition</code> for the case of carrying out an analysis.</p>
resultExpression =
    let results : OrderedSet(ResultExpressionMembership) =
        featureMembersip->
            selectByKind(ResultExpressionMembership) in
    if results->isEmpty() then null
    else results->first().ownedResultExpression
    endif
specializesFromLibrary('AnalysisCases::AnalysisCase')"""
    _resultExpression = EReference(ordered=False, unique=True, containment=False,
                                   derived=True, name='resultExpression', transient=True)

    @property
    def resultExpression(self):
        raise NotImplementedError('Missing implementation for resultExpression')

    @resultExpression.setter
    def resultExpression(self, value):
        raise NotImplementedError('Missing implementation for resultExpression')

    def __init__(self, *, resultExpression=None, **kwargs):

        super().__init__(**kwargs)

        if resultExpression is not None:
            self.resultExpression = resultExpression


class ConcernDefinition(RequirementDefinition):
    """<p>A <code>ConcernDefinition</code> is a <code>RequirementDefinition</code> that one or more stakeholders may be interested in having addressed. These stakeholders are identified by the <code>ownedStakeholders</code>of the <code>ConcernDefinition</code>.</p>

specializesFromLibrary('Requirements::ConcernCheck')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)


class DerivedFlowend(EDerivedCollection):
    pass


class FlowDefinition(ActionDefinition, Interaction):
    """<p>A <code>FlowDefinition</code> is an <code>ActionDefinition</code> that is also an <code>Interaction</code> (which is both a KerML <code>Behavior</code> and <code>Association</code>), representing flows between <code>Usages</code>.</p>
specializesFromLibrary('Flows::MessageAction')
flowEnd->size() = 2 implies
    specializesFromLibrary('Flows::Message')
flowEnd->size() <= 2"""
    flowEnd = EReference(ordered=False, unique=True, containment=False,
                         derived=True, upper=-1, transient=True, derived_class=DerivedFlowend)

    def __init__(self, *, flowEnd=None, **kwargs):

        super().__init__(**kwargs)

        if flowEnd:
            self.flowEnd.extend(flowEnd)


class DerivedFlowdefinition(EDerivedCollection):
    pass


class FlowUsage(ConnectorAsUsage, ActionUsage, Flow):
    """<p>A <code>FlowUsage</code> is an <code>ActionUsage</code> that is also a <code>ConnectorAsUsage</code> and a KerML <code>Flow</code>.</p>
specializesFromLibrary('Flows::messages')
ownedEndFeatures->notEmpty() implies
    specializesFromLibrary('Flows::flows')"""
    flowDefinition = EReference(ordered=True, unique=True, containment=False,
                                derived=True, upper=-1, transient=True, derived_class=DerivedFlowdefinition)

    def __init__(self, *, flowDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if flowDefinition:
            self.flowDefinition.extend(flowDefinition)


class DerivedInterfacedefinition(EDerivedCollection):
    pass


class InterfaceUsage(ConnectionUsage):
    """<p>An <code>InterfaceUsage</code> is a Usage of an <code>InterfaceDefinition</code> to represent an interface connecting parts of a system through specific ports.</p>
ownedEndFeature->size() = 2 implies
    specializesFromLibrary('Interfaces::binaryInterfaces')
specializesFromLibrary('Interfaces::interfaces')"""
    interfaceDefinition = EReference(ordered=False, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedInterfacedefinition)

    def __init__(self, *, interfaceDefinition=None, **kwargs):

        super().__init__(**kwargs)

        if interfaceDefinition:
            self.interfaceDefinition.extend(interfaceDefinition)


class DerivedIncludedusecase(EDerivedCollection):
    pass


class UseCaseDefinition(CaseDefinition):
    """<p>A <code>UseCaseDefinition</code> is a <code>CaseDefinition</code> that specifies a set of actions performed by its subject, in interaction with one or more actors external to the subject. The objective is to yield an observable result that is of value to one or more of the actors.</p>

includedUseCase = ownedUseCase->
    selectByKind(IncludeUseCaseUsage).
    useCaseIncluded
specializesFromLibrary('UseCases::UseCase')"""
    includedUseCase = EReference(ordered=True, unique=True, containment=False,
                                 derived=True, upper=-1, transient=True, derived_class=DerivedIncludedusecase)

    def __init__(self, *, includedUseCase=None, **kwargs):

        super().__init__(**kwargs)

        if includedUseCase:
            self.includedUseCase.extend(includedUseCase)


class DerivedVerifiedrequirement(EDerivedCollection):
    pass


class VerificationCaseDefinition(CaseDefinition):
    """<p>A <code>VerificationCaseDefinition</code> is a <code>CaseDefinition</code> for the purpose of verification of the subject of the case against its requirements.</p>
verifiedRequirement =
    if objectiveRequirement = null then OrderedSet{}
    else 
        objectiveRequirement.featureMembership->
            selectByKind(RequirementVerificationMembership).
            verifiedRequirement->asOrderedSet()
    endif
specializesFromLibrary('VerificationCases::VerificationCase')"""
    verifiedRequirement = EReference(ordered=True, unique=True, containment=False,
                                     derived=True, upper=-1, transient=True, derived_class=DerivedVerifiedrequirement)

    def __init__(self, *, verifiedRequirement=None, **kwargs):

        super().__init__(**kwargs)

        if verifiedRequirement:
            self.verifiedRequirement.extend(verifiedRequirement)


class DerivedViewpointstakeholder(EDerivedCollection):
    pass


class ViewpointDefinition(RequirementDefinition):
    """<p>A <code>ViewpointDefinition</code> is a <code>RequirementDefinition</code> that specifies one or more stakeholder concerns that are to be satisfied by creating a view of a model.</p>
viewpointStakeholder = framedConcern.featureMemberhsip->
    selectByKind(StakeholderMembership).
    ownedStakeholderParameter
specializesFromLibrary('Views::ViewpointCheck')"""
    viewpointStakeholder = EReference(ordered=True, unique=True, containment=False,
                                      derived=True, upper=-1, transient=True, derived_class=DerivedViewpointstakeholder)

    def __init__(self, *, viewpointStakeholder=None, **kwargs):

        super().__init__(**kwargs)

        if viewpointStakeholder:
            self.viewpointStakeholder.extend(viewpointStakeholder)


class DerivedConnectionend(EDerivedCollection):
    pass


class ConnectionDefinition(PartDefinition, AssociationStructure):
    """<p>A <code>ConnectionDefinition</code> is a <code>PartDefinition</code> that is also an <code>AssociationStructure</code>. The end <code>Features</code> of a <code>ConnectionDefinition</code> must be <code>Usages</code>.</p>
specializesFromLibrary('Connections::Connection')
ownedEndFeature->size() = 2 implies
    specializesFromLibrary('Connections::BinaryConnection')
isSufficient"""
    connectionEnd = EReference(ordered=True, unique=True, containment=False,
                               derived=True, upper=-1, transient=True, derived_class=DerivedConnectionend)

    def __init__(self, *, connectionEnd=None, **kwargs):

        super().__init__(**kwargs)

        if connectionEnd:
            self.connectionEnd.extend(connectionEnd)


class SatisfyRequirementUsage(RequirementUsage, AssertConstraintUsage):
    """<p>A <code>SatisfyRequirementUsage</code> is an <code>AssertConstraintUsage</code> that asserts, by default, that a satisfied <code>RequirementUsage</code> is true for a specific <code>satisfyingFeature</code>, or, if <code>isNegated = true</code>, that the <code>RequirementUsage</code> is false. The satisfied <code>RequirementUsage</code> is related to the <code>SatisfyRequirementUsage</code> by a <code>ReferenceSubsetting</code> <code>Relationship</code>.</p>
satisfyingFeature =
    let bindings: BindingConnector = ownedMember->
        selectByKind(BindingConnector)->
        select(b | b.relatedElement->includes(subjectParameter)) in
    if bindings->isEmpty() or 
       not bindings->first().relatedElement->exits(r | r <> subjectParameter) 
    then null
    else bindings->first().relatedElement->any(r | r <> subjectParameter)
    endif
ownedMember->selectByKind(BindingConnector)->
    select(b |
        b.relatedElement->includes(subjectParameter) and
        b.relatedElement->exists(r | r <> subjectParameter))->
    size() = 1
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(RequirementUsage)
if isNegated then
    specializesFromLibrary('Requirements::notSatisfiedRequirementChecks')
else
    specializesFromLibrary('Requirements::satisfiedRequirementChecks')
endif"""
    _satisfiedRequirement = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='satisfiedRequirement', transient=True)
    _satisfyingFeature = EReference(
        ordered=False, unique=True, containment=False, derived=True, name='satisfyingFeature', transient=True)

    @property
    def satisfiedRequirement(self):
        raise NotImplementedError('Missing implementation for satisfiedRequirement')

    @satisfiedRequirement.setter
    def satisfiedRequirement(self, value):
        raise NotImplementedError('Missing implementation for satisfiedRequirement')

    @property
    def satisfyingFeature(self):
        raise NotImplementedError('Missing implementation for satisfyingFeature')

    @satisfyingFeature.setter
    def satisfyingFeature(self, value):
        raise NotImplementedError('Missing implementation for satisfyingFeature')

    def __init__(self, *, satisfiedRequirement=None, satisfyingFeature=None, **kwargs):

        super().__init__(**kwargs)

        if satisfiedRequirement is not None:
            self.satisfiedRequirement = satisfiedRequirement

        if satisfyingFeature is not None:
            self.satisfyingFeature = satisfyingFeature


class DerivedAllocation(EDerivedCollection):
    pass


class AllocationDefinition(ConnectionDefinition):
    """<p>An <code>AllocationDefinition</code> is a <code>ConnectionDefinition</code> that specifies that some or all of the responsibility to realize the intent of the <code>source</code> is allocated to the <code>target</code> instances. Such allocations define mappings across the various structures and hierarchies of a system model, perhaps as a precursor to more rigorous specifications and implementations. An <code>AllocationDefinition</code> can itself be refined using nested <code>allocations</code> that give a finer-grained decomposition of the containing allocation mapping.</p>
allocation = usage->selectAsKind(AllocationUsage)
specializesFromLibrary('Allocations::Allocation')"""
    allocation = EReference(ordered=True, unique=True, containment=False,
                            derived=True, upper=-1, transient=True, derived_class=DerivedAllocation)

    def __init__(self, *, allocation=None, **kwargs):

        super().__init__(**kwargs)

        if allocation:
            self.allocation.extend(allocation)


class IncludeUseCaseUsage(UseCaseUsage, PerformActionUsage):
    """<p>An <code>IncludeUseCaseUsage</code> is a <code>UseCaseUsage</code> that represents the inclusion of a <code>UseCaseUsage</code> by a <code>UseCaseDefinition</code> or <code>UseCaseUsage</code>. Unless it is the <code>IncludeUseCaseUsage</code> itself, the <code>UseCaseUsage</code> to be included is related to the <code>includedUseCase</code> by a <code>ReferenceSubsetting</code> <code>Relationship</code>. An <code>IncludeUseCaseUsage</code> is also a PerformActionUsage, with its <code>useCaseIncluded</code> as the <code>performedAction</code>.</p>

owningType <> null and
(owningType.oclIsKindOf(UseCaseDefinition) or
 owningType.oclIsKindOf(UseCaseUsage) implies
    specializesFromLibrary('UseCases::UseCase::includedUseCases')
referencedFeatureTarget() <> null implies
    referencedFeatureTarget().oclIsKindOf(UseCaseUsage)"""
    _useCaseIncluded = EReference(ordered=False, unique=True, containment=False,
                                  derived=True, name='useCaseIncluded', transient=True)

    @property
    def useCaseIncluded(self):
        raise NotImplementedError('Missing implementation for useCaseIncluded')

    @useCaseIncluded.setter
    def useCaseIncluded(self, value):
        raise NotImplementedError('Missing implementation for useCaseIncluded')

    def __init__(self, *, useCaseIncluded=None, **kwargs):

        super().__init__(**kwargs)

        if useCaseIncluded is not None:
            self.useCaseIncluded = useCaseIncluded


class DerivedInterfaceend(EDerivedCollection):
    pass


class InterfaceDefinition(ConnectionDefinition):
    """<p>An <code>InterfaceDefinition</code> is a <code>ConnectionDefinition</code> all of whose ends are <code>PortUsages</code>, defining an interface between elements that interact through such ports.</p>
specializesFromLibrary('Interfaces::Interface')
ownedEndFeature->size() = 2 implies
    specializesFromLibrary('Interfaces::BinaryInterface')"""
    interfaceEnd = EReference(ordered=True, unique=True, containment=False,
                              derived=True, upper=-1, transient=True, derived_class=DerivedInterfaceend)

    def __init__(self, *, interfaceEnd=None, **kwargs):

        super().__init__(**kwargs)

        if interfaceEnd:
            self.interfaceEnd.extend(interfaceEnd)


class SuccessionFlowUsage(FlowUsage, SuccessionFlow):
    """<p>A <code>SuccessionFlowUsage</code> is a <code>FlowUsage</code> that is also a KerML <code>SuccessionFlow</code>.</p>
specializesFromLibrary('Flows::successionFlows')"""

    def __init__(self, **kwargs):

        super().__init__(**kwargs)
