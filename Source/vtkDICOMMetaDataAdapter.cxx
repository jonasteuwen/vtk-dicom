/*=========================================================================

  Program: DICOM for VTK

  Copyright (c) 2012-2019 David Gobbi
  All rights reserved.
  See Copyright.txt or http://dgobbi.github.io/bsd3.txt for details.

     This software is distributed WITHOUT ANY WARRANTY; without even
     the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
     PURPOSE.  See the above copyright notice for more information.

=========================================================================*/
#include "vtkDICOMMetaDataAdapter.h"
#include "vtkDICOMMetaData.h"
#include "vtkDICOMDictionary.h"
#include "vtkDICOMItem.h"
#include "vtkDICOMTagPath.h"

//----------------------------------------------------------------------------
vtkDICOMMetaDataAdapter::vtkDICOMMetaDataAdapter(vtkDICOMMetaData *meta)
{
  this->ConstructionHelper(meta, -1);
}

//----------------------------------------------------------------------------
vtkDICOMMetaDataAdapter::vtkDICOMMetaDataAdapter(
  vtkDICOMMetaData *meta, int i)
{
  this->ConstructionHelper(meta, i);
}

//----------------------------------------------------------------------------
void vtkDICOMMetaDataAdapter::ConstructionHelper(
  vtkDICOMMetaData *meta, int i)
{
  this->Meta = meta;
  this->PerFrame = 0;
  this->Shared = 0;
  this->NullValue = 0;
  this->NumberOfInstances = 0;
  this->MetaInstance = (i >= 0 ? i : 0);

  if (meta)
  {
    meta->Register(0);
    vtkDICOMDataElementIterator iter;
    iter = meta->Find(DC::PerFrameFunctionalGroupsSequence);
    if (iter != meta->End())
    {
      if (iter->IsPerInstance())
      {
        this->PerFrame = &iter->GetValue(this->MetaInstance);
      }
      else
      {
        this->PerFrame = &iter->GetValue();
      }
    }
    iter = meta->Find(DC::SharedFunctionalGroupsSequence);
    if (iter != meta->End())
    {
      if (iter->IsPerInstance())
      {
        this->Shared = &iter->GetValue(this->MetaInstance);
      }
      else
      {
        this->Shared = &iter->GetValue();
      }
    }
  }

  if (this->Shared && this->Shared->IsValid() &&
      this->PerFrame && this->PerFrame->IsValid())
  {
    this->NumberOfInstances = meta->Get(
      this->MetaInstance, DC::NumberOfFrames).AsInt();
    // an invalid value to return when asked for NumberOfFrames
    this->NullValue = new vtkDICOMValue();
  }
  else if (meta)
  {
    this->NumberOfInstances = (i < 0 ? meta->GetNumberOfInstances() : 1);
    this->Shared = 0;
    this->PerFrame = 0;
  }
}

//----------------------------------------------------------------------------
// Copy constructor
vtkDICOMMetaDataAdapter::vtkDICOMMetaDataAdapter(
  const vtkDICOMMetaDataAdapter& other)
  : Meta(other.Meta), PerFrame(other.PerFrame), Shared(other.Shared),
    NullValue(other.NullValue), NumberOfInstances(other.NumberOfInstances),
    MetaInstance(other.MetaInstance)
{
  if (other.Meta)
  {
    this->Meta->Register(0);
  }
  if (this->NullValue)
  {
    this->NullValue = new vtkDICOMValue();
  }
}

//----------------------------------------------------------------------------
// Destructor
vtkDICOMMetaDataAdapter::~vtkDICOMMetaDataAdapter()
{
  if (this->Meta)
  {
    this->Meta->Delete();
  }
  delete this->NullValue;
}

//----------------------------------------------------------------------------
// Assignment
vtkDICOMMetaDataAdapter& vtkDICOMMetaDataAdapter::operator=(
  const vtkDICOMMetaDataAdapter& other)
{
  if (this != &other)
  {
    this->Meta = other.Meta;
    this->PerFrame = other.PerFrame;
    this->Shared = other.Shared;
    this->NullValue = other.NullValue;
    this->NumberOfInstances = other.NumberOfInstances;
    this->MetaInstance = other.MetaInstance;

    if (other.Meta)
    {
      this->Meta->Register(0);
    }
    if (this->NullValue)
    {
      this->NullValue = new vtkDICOMValue();
    }
  }
  return *this;
}

//----------------------------------------------------------------------------
const vtkDICOMValue &vtkDICOMMetaDataAdapter::Get(
  int idx, vtkDICOMTag tag) const
{
  vtkDICOMMetaData *meta = this->Meta;

  if (this->PerFrame)
  {
    // if asked for NumberOfFrames, pretend that it isn't set
    if (tag == DC::NumberOfFrames)
    {
      return *this->NullValue;
    }

    // search PerFrameFunctionalGroupsSequence first,
    // then search SharedFunctionalGroupsSequence
    const vtkDICOMValue *privateValue = 0;
    for (int i = 0; i < 2; i++)
    {
      const vtkDICOMValue *seq = this->PerFrame;
      unsigned int f = idx;

      if (i == 1)
      {
        seq = this->Shared;
        f = 0;
      }

      if (seq && f < seq->GetNumberOfValues())
      {
        // search for the item that matches the frame
        const vtkDICOMItem *items = seq->GetSequenceData();
        const vtkDICOMValue &v = items[f].Get(tag);
        if (v.IsValid())
        {
          return v;
        }
        // search within all the sequences in the item
        vtkDICOMDataElementIterator iter = items[f].Begin();
        vtkDICOMDataElementIterator iterEnd = items[f].End();
        while (iter != iterEnd)
        {
          const vtkDICOMValue &u = iter->GetValue();
          if (u.GetNumberOfValues() == 1)
          {
            const vtkDICOMItem *item = u.GetSequenceData();
            if (item)
            {
              const vtkDICOMValue &w = item->Get(tag);
              if (w.IsValid())
              {
                if ((iter->GetTag().GetGroup() & 1) == 0)
                {
                  return w;
                }
                else if (privateValue == 0)
                {
                  // if we found the attribute in a private sequence,
                  // then save but and keep searching to see if it will
                  // eventually be found somewhere public
                  privateValue = &w;
                }
              }
            }
          }
          ++iter;
        }
      }
    }

    // if it wasn't in a PerFrame or Shared functional group
    const vtkDICOMValue& v = meta->Get(this->MetaInstance, tag);
    if (privateValue && !v.IsValid())
    {
      // attributes found in private parts of the PerFrame or Shared are
      // only returned if the attribute could not be found elsewhere
      return *privateValue;
    }
    return v;
  }

  // if no per-frame data, use file instance
  return meta->Get(idx + this->MetaInstance, tag);
}

//----------------------------------------------------------------------------
const vtkDICOMValue &vtkDICOMMetaDataAdapter::Get(vtkDICOMTag tag) const
{
  return this->Get(0, tag);
}

//----------------------------------------------------------------------------
bool vtkDICOMMetaDataAdapter::Has(vtkDICOMTag tag) const
{
  const vtkDICOMValue& v = this->Get(0, tag);
  return v.IsValid();
}

//----------------------------------------------------------------------------
vtkDICOMTag vtkDICOMMetaDataAdapter::ResolvePrivateTag(
  int idx, vtkDICOMTag ptag, const std::string& creator)
{
  vtkDICOMMetaData *meta = this->Meta;

  if (this->PerFrame)
  {
    // search PerFrameFunctionalGroupsSequence first,
    // then search SharedFunctionalGroupsSequence
    vtkDICOMTag tagFromPrivSeq(0xFFFF,0xFFFF);
    for (int i = 0; i < 2; i++)
    {
      const vtkDICOMValue *seq = this->PerFrame;
      unsigned int f = idx;

      if (i == 1)
      {
        seq = this->Shared;
        f = 0;
      }

      if (seq && f < seq->GetNumberOfValues())
      {
        // search for the item that matches the frame
        const vtkDICOMItem *items = seq->GetSequenceData();
        vtkDICOMTag tag = items[f].ResolvePrivateTag(ptag, creator);
        if (tag != vtkDICOMTag(0xFFFF, 0xFFFF))
        {
          const vtkDICOMValue &v = items[f].Get(tag);
          if (v.IsValid())
          {
            return tag;
          }
        }
        // search within all the sequences in the item
        vtkDICOMDataElementIterator iter = items[f].Begin();
        vtkDICOMDataElementIterator iterEnd = items[f].End();
        while (iter != iterEnd)
        {
          const vtkDICOMValue &u = iter->GetValue();
          if (u.GetNumberOfValues() == 1)
          {
            const vtkDICOMItem *item = u.GetSequenceData();
            if (item)
            {
              tag = item->ResolvePrivateTag(ptag, creator);
              if (tag != vtkDICOMTag(0xFFFF, 0xFFFF))
              {
                const vtkDICOMValue &v = item->Get(tag);
                if (v.IsValid())
                {
                  if ((iter->GetTag().GetGroup() & 1) == 0)
                  {
                    return tag;
                  }
                  else if (tagFromPrivSeq == vtkDICOMTag(0xFFFF, 0xFFFF))
                  {
                    // if desired attribute was found within a private
                    // sequence, we want to keep searching in case it
                    // later appears within a public sequence (this matches
                    // the behavior of GetAttributeValue)
                    tagFromPrivSeq = tag;
                  }
                }
              }
            }
          }
          ++iter;
        }
      }
    }

    // if it wasn't in a PerFrame or Shared functional group
    vtkDICOMTag tag = meta->ResolvePrivateTag(
      this->MetaInstance, ptag, creator);
    if (tag == vtkDICOMTag(0xFFFF, 0xFFFF))
    {
      tag = tagFromPrivSeq;
    }
    return tag;
  }

  // if no per-frame data, use file instance
  return meta->ResolvePrivateTag(idx + this->MetaInstance, ptag, creator);
}

//----------------------------------------------------------------------------
vtkDICOMTag vtkDICOMMetaDataAdapter::ResolvePrivateTag(
  vtkDICOMTag ptag, const std::string& creator)
{
  return this->ResolvePrivateTag(0, ptag, creator);
}
